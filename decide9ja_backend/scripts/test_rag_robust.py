import sys
import os
import time
import asyncio
import logging
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.rag_router import RAGRouter, Intent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("rag_test")

ROBUST_QUESTIONS = [
    # --- PROMPTS FROM CITIZEN PERSPECTIVE (PIDGIN & LOCAL) ---
    "Wetin concern budget with me?",
    "How much dem wan spend for road inside Lagos?",
    "Who carry our money go?",
    "Abeg show me allocation for my local government.",
    "Any money for youth empowerment?",
    "Wetin be the budget for 'Stomach Infrastructure'?",
    "Did they budget for 'Generator' maintenance?",
    "How much for 'Refreshment' and 'Meals'?",
    "Who get the highest allocation for 2026?",
    "Is the budget realistic?",
    
    # --- ACCOUNTABILITY & GOVERNANCE ---
    "Who is responsible for the bad roads in Surulere?",
    "Did my senator deliver the constituency project in Borno South?",
    "Show me the breakdown of the Governor's security vote.",
    "Why is the Ministry of Works spending so much on 'Consultancy'?",
    "List all companies paid for 'Borehole' construction.",
    "Who approved the payment to 'DANTATA & SAWOE'?",
    "Are there any red flags for the Ministry of Power?",
    "Show me duplicate payments in the transaction records.",
    "Which MDA has the most suspicious findings?",
    "Is there any evidence of contract splitting?",

    # --- ECONOMIC REALITY ---
    "Why is rice so expensive in the market?",
    "How much did we borrow in 2025?",
    "What is the debt service allocation for 2026?",
    "Compare the budget for Agriculture vs Defence.",
    "Is there any subsidy in the 2026 budget?",
    "How much is allocated for 'Social Investment Programs'?",
    "What is the exchange rate assumption in the budget?",
    "Show me the capital vs recurrent expenditure ratio.",
    "How much is the personnel cost for the Presidency?",
    "Did the allocation for Health increase or decrease?",

    # --- SPECIFIC BUDGET LINE ITEMS (Gap 5) ---
    "How much did Lagos budget for health in 2026?",
    "What is the total budget for Borno State in 2026?",
    "How much was allocated for education in Adamawa?",
    "Show me the capital expenditure for Works in Rivers.",
    "Did Enugu budget for any new hospitals in 2026?",
    "How much is the personnel cost for Lagos Ministry of Education?",
    "What is the allocation for the Governor's Office in Yobe?",
    "Find budget items related to 'Borehole' in Jigawa.",
    "How much for 'Feeding' in Katsina budget?",
    "What is the biggest project in the 2026 Budget for Anambra?",
    
    # --- FINANCIAL INTELLIGENCE (Gap 7) ---
    "Show me suspicious payments in Lagos.",
    "Who are the top contractors receiving payments recently?",
    "Did 'Julius Berger' receive any money in 2025?",
    "Show me payments above 1 billion naira.",
    "Are there any anomalies in travel expenses?",
    "Find payments to 'Unknown' beneficiaries.",
    "Show me budget items with amount 0.",
    "Who signed the 2026 budget?",
    "What is the code for Ministry of Health?",
    "Show me the overhead cost for the Judiciary.",
    
    # --- OPENTREASURY (Gap 8) ---
    "Who received payments from the Federal Government yesterday?",
    "Show me payments to 'CCECC'.",
    "How much was paid for 'Conference' in 2025?",
    "Did the State House receive any payments recently?",
    "What did the Ministry of Power spend money on in April 2025?",
    "Show payments made to individuals instead of companies.",
    "List payments for 'Diesel' or 'Fuel'.",
    "Did any payment references mention 'Estacode'?",
    "Who authorized the payment for 'Legislative Aides'?",
    "What is the total amount paid to 'Julius Berger'?",

    # --- CIVIC DUTIES & CONSTITUTION ---
    "How do I recall my senator?",
    "What are the requirements to run for Governor?",
    "Does the constitution allow for state police?",
    "What is the role of the Local Government Chairman?",
    "How can I report a corrupt official?",
    "Is it legal for the Governor to appoint his son?",
    "What does 'Federal Character' mean?",
    "Who confirms the appointment of Ministers?",
    "Can the President spend money without approval?",
    "What is the punishment for budget padding?",

    # --- GENERAL KNOWLEDGE (Baseline) ---
    "Who is the current President of Nigeria?",
    "Who is the Governor of Lagos State?",
    "When did Nigeria gain independence?",
    "List all states in the South West region.",
    "Who is the Senate President?",
    "What is the capital of Zamfara?",
    "Who is the Minister of Finance?",
    "How many local governments are in Kano?",
    "Who is the governor of Borno?",
    "What political party is in power in Oyo state?",
    
    # --- CONTEXTual / MIXED HOPS ---
    "Compare the budget for Education in Lagos vs Kano.",
    "Who is the Senator for Borno South and what projects are in his constituency?",
    "Has the budget for 'Roads' increased in 2026?",
    "Show me forensic findings related to the 'Subsidy' removal.",
    "What are the major risks identified in the 2024 audit?",
    "Is there a budget for 'Renewable Energy' in the 2026 plan?",
    "Who controls the budget for the 'FCT'?",
    "Tell me about Bola Ahmed Tinubu and his budget execution.",
    "What is the relationship between the budget and actual spending for Health?",
    "Are there any budget items for 'Security' in states with high violence?"
    
    # Total: ~80 questions
]

async def run_robust_test():
    print(f"🚀 Starting RAG ROBUSTNESS TEST ({len(ROBUST_QUESTIONS)} Questions)")
    print("="*80)
    
    db = SessionLocal()
    # Initialize real router
    router = RAGRouter(db)
    
    results = {
        "total": 0,
        "success": 0,
        "sources": {},
        "intents": {},
        "times": [],
        "failures": []
    }
    
    start_time = time.time()
    
    # Semaphore to control concurrency
    sem = asyncio.Semaphore(10)

    async def process_question(i, q):
        async with sem:
            try:
                t0 = time.time()
                # USE ROUTER
                result = await router.route(q, filters={}, chat_history=[])
                elapsed = time.time() - t0
                
                # Analyze result
                response = result.get("response", "")
                intent = result.get("intent", "unknown")
                sources = result.get("sources", [])
                context = result.get("context", "")
                language = result.get("language", "en") 
                
                source_types = list(set(s.get('doc_type', 'unknown') for s in sources))
                
                # Print progress (atomic print not guaranteed but good enough)
                print(f"[{i+1}/{len(ROBUST_QUESTIONS)}] ✅ {elapsed:.2f}s | {intent:<10} | {language:<6} | Src: {len(sources)}")
                
                context_len = len(context) if context else 0
                success = "I'm having trouble finding" not in response and context_len > 50
                
                return {
                    "success": success,
                    "elapsed": elapsed,
                    "intent": intent,
                    "language": language,
                    "source_types": source_types,
                    "q": q,
                    "reason": "low_context_or_fallback" if not success else None
                }

            except Exception as e:
                print(f"[{i+1}/{len(ROBUST_QUESTIONS)}] ❌ Error: {e}")
                return {
                    "success": False,
                    "q": q,
                    "reason": str(e)
                }

    # Launch all tasks
    tasks = [process_question(i, q) for i, q in enumerate(ROBUST_QUESTIONS)]
    results_list = await asyncio.gather(*tasks)
    
    # Aggregate results
    for res in results_list:
        results["total"] += 1
        if res["success"]:
            results["success"] += 1
            results["times"].append(res["elapsed"])
            results["intents"][res["intent"]] = results["intents"].get(res["intent"], 0) + 1
            for s in res["source_types"]:
                results["sources"][s] = results["sources"].get(s, 0) + 1
        else:
            results["failures"].append({"q": res["q"], "reason": res["reason"], "intent": res.get("intent", "error")})

    print("\n" + "="*80)
    print("📊 TEST REPORT")
    print(f"Total Questions: {results['total']}")
    print(f"Success Rate:    {results['success']}/{results['total']} ({(results['success']/results['total'])*100:.1f}%)")
    if results["times"]:
        print(f"Avg Time:        {sum(results['times'])/len(results['times']):.3f}s")
        print(f"Total Duration:  {time.time() - start_time:.2f}s")
    
    print("\nIntent Distribution:")
    for i, count in results["intents"].items():
        print(f"  - {i}: {count}")

    print("\nSource Distribution:")
    for s, count in results["sources"].items():
        print(f"  - {s}: {count}")
        
    if results["failures"]:
        print("\n❌ Failures/Weaknesses:")
        for f in results["failures"][:15]:
            print(f"  - {f['q']} ([{f.get('intent', 'error')}])")
            
    print("="*80)
    db.close()

if __name__ == "__main__":
    asyncio.run(run_robust_test())
