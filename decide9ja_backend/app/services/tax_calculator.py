"""
Tax Calculator Service (Nigeria PAYE)
Calculates Personal Income Tax based on PITA (Personal Income Tax Act).
"""

def calculate_paye(annual_gross_income: float) -> dict:
    """
    Calculate PAYE tax for a given annual gross income.
    
    Rules (Simplified PITA):
    1. Consolidated Relief Allowance (CRA): Higher of 200,000 or 1% of Gross Income + 20% of Gross Income.
    2. Taxable Income = Gross Income - CRA - Pension/NHF (Assuming 8% pension, 2.5% NHF not auto-deducted here, kept simple).
       *For simplicity, we only deduct CRA in this V1 calculator.*
    3. Tax Bands:
       - First 300,000 @ 7%
       - Next 300,000 @ 11%
       - Next 500,000 @ 15%
       - Next 500,000 @ 19%
       - Next 1,600,000 @ 21%
       - Above 3,200,000 (cumulative) @ 24%
    
    Minimum Tax: 1% of Gross Income (if taxable income is too low).
    """
    
    # 1. Consolidated Relief Allowance (CRA)
    cra_fixed = 200000.0
    cra_percent = 0.01 * annual_gross_income
    base_relief = max(cra_fixed, cra_percent)
    variable_relief = 0.20 * annual_gross_income
    
    total_relief = base_relief + variable_relief
    
    # 2. Taxable Income
    taxable_income = max(0, annual_gross_income - total_relief)
    
    # 3. Calculate Tax 
    tax = 0.0
    remaining = taxable_income
    
    # Band 1: First 300k @ 7%
    if remaining > 0:
        chunk = min(remaining, 300000)
        tax += chunk * 0.07
        remaining -= chunk
        
    # Band 2: Next 300k @ 11%
    if remaining > 0:
        chunk = min(remaining, 300000)
        tax += chunk * 0.11
        remaining -= chunk

    # Band 3: Next 500k @ 15%
    if remaining > 0:
        chunk = min(remaining, 500000)
        tax += chunk * 0.15
        remaining -= chunk
        
    # Band 4: Next 500k @ 19%
    if remaining > 0:
        chunk = min(remaining, 500000)
        tax += chunk * 0.19
        remaining -= chunk

    # Band 5: Next 1.6M @ 21%
    if remaining > 0:
        chunk = min(remaining, 1600000)
        tax += chunk * 0.21
        remaining -= chunk
        
    # Band 6: Above @ 24%
    if remaining > 0:
        tax += remaining * 0.24
        
    # Minimum Tax Check
    min_tax = 0.01 * annual_gross_income
    final_tax = max(tax, min_tax)
    
    return {
        "annual_gross": annual_gross_income,
        "consolidated_relief": total_relief,
        "taxable_income": taxable_income,
        "annual_tax_payable": final_tax,
        "monthly_tax_payable": final_tax / 12,
        "effective_tax_rate": (final_tax / annual_gross_income * 100) if annual_gross_income > 0 else 0
    }

if __name__ == "__main__":
    # Test
    salary = 6000000 # 6M annual
    result = calculate_paye(salary)
    print(f"Salary: {salary:,.2f}")
    print(f"Tax: {result['annual_tax_payable']:,.2f}")
    print(f"Monthly: {result['monthly_tax_payable']:,.2f}")
