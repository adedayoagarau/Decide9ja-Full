/**
 * Financial Intelligence API Client
 * Gap 9: Frontend Integration
 */

export interface FinancialSearchResponse {
    metadata: {
        query: string;
        total_returned: number;
        generated_at: string;
    };
    results: FinancialItem[];
}

export interface FinancialItem {
    id: string | number;
    source_type: 'finding' | 'budget' | 'transaction';
    main_text: string;
    sub_text: string;
    amount?: number;
    year: number;
    jurisdiction: string;
    risk_score?: number;
    automated_insights?: string[];
}

export interface StateSummary {
    state: string;
    year: number;
    total_budget: number;
    line_items: number;
    top_mdas: { mda: string; total: number }[];
}

const API_BASE = '/api/budget';

export const FinancialAPI = {
    /**
     * Unified search for financial data (neutral + insights)
     */
    async search(query: string, limit = 20): Promise<FinancialSearchResponse> {
        const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&limit=${limit}`);
        if (!res.ok) throw new Error('Search failed');
        return res.json();
    },

    /**
     * Get Red Flag/High Risk items
     */
    async getRedFlags(jurisdiction?: string, limit = 50): Promise<FinancialSearchResponse> {
        const url = jurisdiction
            ? `${API_BASE}/red-flags?jurisdiction=${encodeURIComponent(jurisdiction)}&limit=${limit}`
            : `${API_BASE}/red-flags?limit=${limit}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch red flags');
        return res.json();
    },

    /**
     * Get summary statistics for a state
     */
    async getStateSummary(state: string, year = 2026): Promise<StateSummary> {
        const res = await fetch(`${API_BASE}/state/${encodeURIComponent(state)}?year=${year}`);
        if (!res.ok) throw new Error('Failed to fetch state summary');
        return res.json();
    }
};
