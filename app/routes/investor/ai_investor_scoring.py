import json
from app.routes.extensions import get_gemini_client
from google.genai import types

def get_investor_data_for_scoring(email: str, db_connection) -> dict:
    """
    Fetch and structure investor profile and portfolio data for scoring.
    """
    cursor = db_connection.cursor(dictionary=True)

    # Fetch investor profile
    cursor.execute("SELECT * FROM investor_profiles WHERE email = %s", (email,))
    profile = cursor.fetchone() or {}

    # Fetch investor portfolio
    cursor.execute("SELECT * FROM investor_portfolio WHERE investor_email = %s", (email,))
    portfolio = cursor.fetchall() or []

    cursor.close()

    # Prepare structured data for Gemini
    investor_data = {
        "investor_profile": {
            "name": profile.get("full_name"),
            "bio": profile.get("bio"),
            "location": profile.get("location"),
            "investment_stage": profile.get("preferred_investment_stage"),
            "investment_range": f"${profile.get('min_ticket_size', 0)} - ${profile.get('max_ticket_size', 0)}",
            "sectors": profile.get("investment_focus", "").split(","),
            "years_experience": profile.get("years_of_experience")
        },
        "portfolio": [
            {
                "startup_name": p.get("startup_name"),
                "sector": p.get("sector"),
                "stage": p.get("investment_stage"),
                "outcome": p.get("outcome")
            } for p in portfolio
        ]
    }
    return investor_data

def compute_and_save_investor_profile_score(email: str, db_connection):
    """
    Call Gemini to get a profile score for the investor and save it to the database.
    """
    try:
        investor_data = get_investor_data_for_scoring(email, db_connection)
        investor_json = json.dumps(investor_data, indent=2)

        prompt_template = """
You are an investment platform evaluation system.

Your task is to calculate an Investor Profile Score between 0 and 95.

Evaluate the investor based on the following criteria:

1.  **Profile completeness (0–15)**: How complete is the profile? (name, bio, location, etc.)
2.  **Investment focus clarity (0–15)**: Is it clear what sectors and stages they invest in?
3.  **Portfolio credibility (0–20)**: Does the portfolio seem real and aligned with their focus?
4.  **Sector expertise relevance (0–15)**: Does their experience and portfolio support their stated sector focus?
5.  **Investment stage clarity (0–10)**: Is the investment stage clearly defined?
6.  **Experience and track record (0–10)**: How much experience do they have?
7.  **Geographic clarity and reach (0–10)**: Is their geographic focus clear?

**Rules:**
- Never give a score above 95.
- Return only a valid JSON response.
- Be strict and realistic in evaluation.

**Output format:**
```json
{
  "profile_score": number,
  "score_breakdown": {
    "profile_completeness": number,
    "investment_focus": number,
    "portfolio_strength": number,
    "sector_expertise": number,
    "stage_clarity": number,
    "experience": number,
    "geographic_presence": number
  },
  "summary": "short explanation"
}
```
"""
        prompt = f"{prompt_template}\\n\\nInvestor data:\\n{investor_json}"

        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=1024,
                temperature=0.1,
            )
        )

        result_text = response.text.strip()
        # Clean the response to ensure it's valid JSON
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()
        
        # Verify JSON is complete before parsing
        if not result_text.strip().endswith("}"):
            print(f"❌ Incomplete JSON response for {email}")
            print(f"   Response does not end with closing brace: {result_text[-50:]}")
            return
        
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON response for {email}: {e}")
            print(f"   Response was: {result_text}")
            return
        
        score = result.get("profile_score")
        breakdown = json.dumps(result.get("score_breakdown"))
        summary = result.get("summary")

        if score is not None:
            cursor = db_connection.cursor()
            cursor.execute("""
                UPDATE investor_profiles
                SET profile_score = %s,
                    profile_score_breakdown = %s,
                    profile_score_summary = %s
                WHERE email = %s
            """, (score, breakdown, summary, email))
            db_connection.commit()
            cursor.close()
            print(f"✅ Investor profile score saved for {email}: {score}")
        else:
            print(f"⚠️ Gemini response for {email} did not contain a profile score.")

    except Exception as e:
        print(f"❌ Error in Gemini scoring for investor {email}: {e}")