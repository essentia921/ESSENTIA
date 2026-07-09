import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

interface Account {
  id: number;
  name: string;
  has_token: boolean;
}

interface Profile {
  profileId: string;
  countryCode: string;
  marketplace?: string;
  accountId?: string;
  region?: string;
  is_selected?: boolean;
}

interface Campaign {
  campaignId: string;
  name: string;
  state: string;
  budget?: number;
  profileId?: string;
  is_selected?: boolean;
}

interface SelectionContextType {
  selectedAccount: Account | null;
  setSelectedAccount: (account: Account | null) => void;
  selectedProfiles: Profile[];
  setSelectedProfiles: (profiles: Profile[]) => void;
  selectedCampaigns: Campaign[];
  setSelectedCampaigns: (campaigns: Campaign[]) => void;
  clearSelections: () => void;
  // Legacy compatibility
  selectedProfile: Profile | null;
  setSelectedProfile: (profile: Profile | null) => void;
}

const SelectionContext = createContext<SelectionContextType | undefined>(undefined);

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selectedAccount, setSelectedAccountRaw] = useState<Account | null>(() => {
    const saved = localStorage.getItem('selectedAccount');
    return saved ? JSON.parse(saved) : null;
  });
  
  const [selectedProfiles, setSelectedProfiles] = useState<Profile[]>(() => {
    const saved = localStorage.getItem('selectedProfiles');
    if (saved) return JSON.parse(saved);
    const legacySaved = localStorage.getItem('selectedProfile');
    return legacySaved ? [JSON.parse(legacySaved)] : [];
  });
  
  const [selectedCampaigns, setSelectedCampaignsRaw] = useState<Campaign[]>(() => {
    const saved = localStorage.getItem('selectedCampaigns');
    return saved ? JSON.parse(saved) : [];
  });
  
  const setSelectedCampaigns = (campaigns: Campaign[]) => {
    setSelectedCampaignsRaw(campaigns);
  };

  useEffect(() => {
    if (selectedCampaigns.length > 0) {
      const selectedProfileIds = new Set(selectedProfiles.map(p => p.profileId));
      const invalidCampaigns = selectedCampaigns.filter(c => 
        !c.profileId || !selectedProfileIds.has(c.profileId)
      );
      
      if (invalidCampaigns.length > 0) {
        const validCampaigns = selectedCampaigns.filter(c => 
          c.profileId && selectedProfileIds.has(c.profileId)
        );
        setSelectedCampaignsRaw(validCampaigns);
      }
    }
  }, [selectedProfiles]);

  useEffect(() => {
    if (selectedAccount) {
      localStorage.setItem('selectedAccount', JSON.stringify(selectedAccount));
    } else {
      localStorage.removeItem('selectedAccount');
    }
  }, [selectedAccount]);

  useEffect(() => {
    if (selectedProfiles.length > 0) {
      localStorage.setItem('selectedProfiles', JSON.stringify(selectedProfiles));
      localStorage.removeItem('selectedProfile');
    } else {
      localStorage.removeItem('selectedProfiles');
    }
  }, [selectedProfiles]);

  useEffect(() => {
    const campaigns = selectedCampaigns;
    if (campaigns.length > 0) {
      localStorage.setItem('selectedCampaigns', JSON.stringify(campaigns));
    } else {
      localStorage.removeItem('selectedCampaigns');
    }
  }, [selectedCampaigns]);

  const setSelectedAccount = (account: Account | null) => {
    if (account?.id !== selectedAccount?.id) {
      setSelectedProfiles([]);
      setSelectedCampaignsRaw([]);
    }
    setSelectedAccountRaw(account);
  };

  const clearSelections = () => {
    setSelectedAccountRaw(null);
    setSelectedProfiles([]);
    setSelectedCampaignsRaw([]);
    localStorage.removeItem('selectedAccount');
    localStorage.removeItem('selectedProfiles');
    localStorage.removeItem('selectedProfile');
    localStorage.removeItem('selectedCampaigns');
  };

  const selectedProfile = selectedProfiles.length > 0 ? selectedProfiles[0] : null;
  
  const setSelectedProfile = (profile: Profile | null) => {
    if (profile) {
      setSelectedProfiles([profile]);
    } else {
      setSelectedProfiles([]);
    }
  };

  return (
    <SelectionContext.Provider
      value={{
        selectedAccount,
        setSelectedAccount,
        selectedProfiles,
        setSelectedProfiles,
        selectedCampaigns,
        setSelectedCampaigns,
        clearSelections,
        selectedProfile,
        setSelectedProfile,
      }}
    >
      {children}
    </SelectionContext.Provider>
  );
}

export function useSelection() {
  const context = useContext(SelectionContext);
  if (context === undefined) {
    throw new Error('useSelection must be used within a SelectionProvider');
  }
  return context;
}
