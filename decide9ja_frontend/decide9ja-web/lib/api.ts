/**
 * API client for Decide9ja FastAPI backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Types
export interface Politician {
    id: string;
    name: string;
    position: string;
    party: string;
    state: string;
    constituency?: string;
    imageUrl?: string;
    bio?: string;
    promiseScore?: number;
    term_start?: string;
    term_end?: string;
}

export interface Representative {
    level: 'federal' | 'state' | 'local';
    position: string;
    politician: Politician;
}

export interface Issue {
    issue_id: string;
    title: string;
    domain: string;
    severity: 'low' | 'moderate' | 'severe';
    status: 'active' | 'resolved' | 'archived';
    location?: string;
    states?: string[];
    summary?: string;
    confidence?: number;
    verified?: boolean;
    event_count?: number;
    first_reported?: string;
    last_updated?: string;
    // For detail view
    events?: IssueEvent[];
    politicians?: IssuePolitician[];
}

export interface IssueEvent {
    event_id: string;
    title: string;
    description?: string;
    event_date?: string;
    event_type: string;
    source_url?: string;
    source_name?: string;
}

export interface IssuePolitician {
    slug: string;
    name: string;
    party: string;
    position: string;
    role: string;
    mention_count: number;
}

export interface Stats {
    politiciansCount: number;
    statesCount: number;
    issuesCount: number;
    usersCount: number;
}

// API Client
export const api = {
    // Politicians
    politicians: {
        list: async (params?: Record<string, string>): Promise<Politician[]> => {
            const url = new URL(`${API_BASE}/api/politicians`);
            if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
            const res = await fetch(url.toString());
            return res.json();
        },

        get: async (id: string): Promise<Politician> => {
            const res = await fetch(`${API_BASE}/api/politicians/${id}`);
            return res.json();
        },

        search: async (query: string): Promise<Politician[]> => {
            const res = await fetch(`${API_BASE}/api/politicians/search?q=${encodeURIComponent(query)}`);
            return res.json();
        },

        issues: async (slug: string): Promise<Issue[]> => {
            const res = await fetch(`${API_BASE}/api/issues/politician/${encodeURIComponent(slug)}`);
            const data = await res.json();
            return data.issues || [];
        },
    },

    // Representatives by location
    representatives: {
        byLocation: async (state: string, lga: string): Promise<Representative[]> => {
            const res = await fetch(`${API_BASE}/api/representatives?state=${encodeURIComponent(state)}&lga=${encodeURIComponent(lga)}`);
            return res.json();
        },
    },

    // Issues
    issues: {
        list: async (params?: Record<string, string>): Promise<Issue[]> => {
            const url = new URL(`${API_BASE}/api/issues`);
            if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
            const res = await fetch(url.toString());
            if (!res.ok) return [];
            return res.json();
        },

        get: async (id: string): Promise<Issue | null> => {
            const res = await fetch(`${API_BASE}/api/issues/${id}`);
            if (!res.ok) return null;
            return res.json();
        },

        trending: async (limit: number = 5): Promise<Issue[]> => {
            const res = await fetch(`${API_BASE}/api/issues/trending?limit=${limit}`);
            if (!res.ok) return [];
            return res.json();
        },

        domains: async (): Promise<{ domain: string; count: number }[]> => {
            const res = await fetch(`${API_BASE}/api/issues/domains`);
            if (!res.ok) return [];
            const data = await res.json();
            return data.domains || [];
        },
    },

    // Stats
    stats: {
        overview: async (): Promise<Stats> => {
            const res = await fetch(`${API_BASE}/api/stats`);
            return res.json();
        },
    },

    // States and LGAs
    locations: {
        states: async (): Promise<string[]> => {
            const res = await fetch(`${API_BASE}/api/states`);
            if (!res.ok) {
                // Fallback to hardcoded list
                return NIGERIAN_STATES;
            }
            return res.json();
        },

        lgas: async (state: string): Promise<string[]> => {
            const res = await fetch(`${API_BASE}/api/states/${encodeURIComponent(state)}/lgas`);
            if (!res.ok) {
                // Fallback
                return STATE_LGAS[state] || [];
            }
            return res.json();
        },
    },

    // Admin endpoints
    admin: {
        overview: async (): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/admin/overview`);
            return res.json();
        },

        stats: async (days: number = 7): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/admin/stats?days=${days}`);
            return res.json();
        },

        issueAnalytics: async (): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/admin/issues/analytics`);
            return res.json();
        },
    },
};

// Fallback data
export const NIGERIAN_STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
    "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT", "Gombe",
    "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara",
    "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau",
    "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"
];

export const STATE_LGAS: Record<string, string[]> = {
    "Lagos": ["Agege", "Ajeromi-Ifelodun", "Alimosho", "Amuwo-Odofin", "Apapa", "Badagry", "Epe", "Eti-Osa", "Ibeju-Lekki", "Ifako-Ijaiye", "Ikeja", "Ikorodu", "Kosofe", "Lagos Island", "Lagos Mainland", "Mushin", "Ojo", "Oshodi-Isolo", "Shomolu", "Surulere"],
    "Ogun": ["Abeokuta North", "Abeokuta South", "Ado-Odo/Ota", "Ewekoro", "Ifo", "Ijebu East", "Ijebu North", "Ijebu North East", "Ijebu Ode", "Ikenne", "Imeko Afon", "Ipokia", "Obafemi Owode", "Odeda", "Odogbolu", "Ogun Waterside", "Remo North", "Sagamu", "Yewa North", "Yewa South"],
    "Rivers": ["Abua-Odual", "Ahoada East", "Ahoada West", "Akuku-Toru", "Andoni", "Asari-Toru", "Bonny", "Degema", "Eleme", "Emohua", "Etche", "Gokana", "Ikwerre", "Khana", "Obio-Akpor", "Ogba-Egbema-Ndoni", "Ogu-Bolo", "Okrika", "Omuma", "Opobo-Nkoro", "Oyigbo", "Port Harcourt", "Tai"],
    "Kano": ["Ajingi", "Albasu", "Bagwai", "Bebeji", "Bichi", "Bunkure", "Dala", "Dambatta", "Dawakin Kudu", "Dawakin Tofa", "Doguwa", "Fagge", "Gabasawa", "Garko", "Garun Mallam", "Gaya", "Gezawa", "Gwale", "Gwarzo", "Kabo", "Kano Municipal", "Karaye", "Kibiya", "Kiru", "Kumbotso", "Kunchi", "Kura", "Madobi", "Makoda", "Minjibir", "Nasarawa", "Rano", "Rimin Gado", "Rogo", "Shanono", "Sumaila", "Takai", "Tarauni", "Tofa", "Tsanyawa", "Tudun Wada", "Ungogo", "Warawa", "Wudil"],
    "FCT": ["Abaji", "Bwari", "Gwagwalada", "Kuje", "Kwali", "Municipal Area Council"],
};

// Party colors
export const PARTY_COLORS: Record<string, string> = {
    "APC": "#1e3a8a",
    "PDP": "#dc2626",
    "LP": "#16a34a",
    "NNPP": "#7c3aed",
    "APGA": "#f59e0b",
    "SDP": "#0ea5e9",
};

export function getPartyColor(party: string): string {
    return PARTY_COLORS[party.toUpperCase()] || "#6b7280";
}
