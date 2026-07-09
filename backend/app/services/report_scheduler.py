"""
Report Scheduler - Clean polling for report status

Responsibility: Only poll PENDING reports and download when COMPLETED.
Does NOT call bid_analyzer or save planned_actions.
"""

import logging
import threading
from typing import Dict

from db.accounts_db import (
    get_reports_by_status,
    save_report_data,
    set_report_status as db_set_report_status,
    get_client_tokens,
    get_profile_info,
    update_client_tokens,
    get_runs_by_status,
    set_run_status,
    get_reports_for_run,
)
from backend.app.services.amazon_reports import (
    check_report_status as amazon_check_status,
    download_and_parse,
)
from backend.app.services.amazon import get_api_url_for_country, AmazonAdsService

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 600


def poll_reports_once() -> Dict:
    """
    Poll all reports with status PENDING, check Amazon status.
    If COMPLETED, download, parse and save data. Set status to PARSED.
    If FAILED, set status to FAILED.
    
    Returns:
        Dict with poll results
    """
    pending_reports = get_reports_by_status("PENDING")
    
    if not pending_reports:
        logger.info("No pending reports to poll")
        return {"polled": 0, "parsed": 0, "failed": 0}
    
    logger.info(f"Polling {len(pending_reports)} pending reports")
    
    parsed_count = 0
    failed_count = 0
    
    for report in pending_reports:
        report_id = report.get("report_id")
        profile_id = report.get("profile_id")
        account_id = report.get("account_id")
        
        try:
            tokens = get_client_tokens(account_id)
            if not tokens or not tokens.get("access_token"):
                logger.warning(f"No tokens for account {account_id}, skipping report {report_id}")
                continue
            
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            
            profile_info = get_profile_info(account_id, profile_id)
            api_url = None
            if profile_info:
                api_url = profile_info.get('api_url')
                if not api_url and profile_info.get('country_code'):
                    api_url = get_api_url_for_country(profile_info['country_code'])
            if not api_url:
                api_url = "https://advertising-api-eu.amazon.com"
            
            status_data = amazon_check_status(access_token, profile_id, api_url, report_id)
            status = status_data.get("status")
            
            if status in ["PENDING", "PROCESSING"]:
                logger.info(f"Report {report_id} still {status}")
                continue
            
            elif status in ["COMPLETED", "SUCCESS"]:
                download_url = status_data.get("url")
                if download_url:
                    report_data = download_and_parse(download_url)
                    save_report_data(report_id, report_data)
                    logger.info(f"Report {report_id} parsed and saved")
                    parsed_count += 1
                else:
                    logger.warning(f"Report {report_id} completed but no download URL")
            
            elif status == "FAILURE":
                db_set_report_status(report_id, "FAILED")
                logger.error(f"Report {report_id} failed: {status_data.get('failureReason')}")
                failed_count += 1
            
        except Exception as e:
            logger.error(f"Error polling report {report_id}: {e}")
            continue
    
    return {
        "polled": len(pending_reports),
        "parsed": parsed_count,
        "failed": failed_count
    }


def mark_runs_ready_once() -> Dict:
    """
    Check runs with status REPORTS_PENDING.
    If both 14D and 30D reports are PARSED, set run to REPORTS_READY.
    
    Returns:
        Dict with results
    """
    runs = get_runs_by_status(["REPORTS_PENDING"])
    
    if not runs:
        logger.info("No runs waiting for reports")
        return {"checked": 0, "marked_ready": 0}
    
    logger.info(f"Checking {len(runs)} runs for report completion")
    
    marked_ready = 0
    
    for run in runs:
        run_id = run.get("id")
        
        reports = get_reports_for_run(run_id)
        report_30 = reports.get("30")
        
        # Only check 30D report (14D removed per user request)
        reports_ready = False
        
        if report_30:
            status = report_30.get("status")
            # Accept PARSED or COMPLETED as valid ready states
            if status in ("PARSED", "COMPLETED"):
                reports_ready = True
        
        if reports_ready:
            set_run_status(run_id, "REPORTS_READY")
            logger.info(f"Run {run_id} marked REPORTS_READY")
            marked_ready += 1
    
    return {
        "checked": len(runs),
        "marked_ready": marked_ready
    }


# Legacy functions for backwards compatibility
def process_pending_reports():
    """Legacy function - calls poll_reports_once."""
    return poll_reports_once()


class ReportPollerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
    
    def stop(self):
        self._stop_event.set()
    
    def run(self):
        logger.info("Report poller thread started")
        while not self._stop_event.is_set():
            try:
                poll_reports_once()
                mark_runs_ready_once()
            except Exception as e:
                logger.error(f"Error in report poller: {e}")
            
            self._stop_event.wait(POLL_INTERVAL_SECONDS)
        
        logger.info("Report poller thread stopped")


_poller_thread = None


def start_report_poller():
    global _poller_thread
    if _poller_thread is None or not _poller_thread.is_alive():
        _poller_thread = ReportPollerThread()
        _poller_thread.start()
        logger.info("Report poller started")


def stop_report_poller():
    global _poller_thread
    if _poller_thread and _poller_thread.is_alive():
        _poller_thread.stop()
        _poller_thread.join(timeout=5)
        logger.info("Report poller stopped")
