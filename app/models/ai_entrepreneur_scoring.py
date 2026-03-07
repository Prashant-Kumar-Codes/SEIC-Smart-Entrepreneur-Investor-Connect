import json
import logging
from ..routes.extensions import get_gemini_client
from google.genai import types

# Configure logging
logger = logging.getLogger(__name__)

def get_entrepreneur_data_for_scoring(email: str, db_connection) -> dict:
    """
    Fetch and structure entrepreneur profile and pitch data for scoring.
    Returns empty dict if no data found.
    """
    try:
        cursor = db_connection.cursor(dictionary=True)

        # Fetch entrepreneur profile
        cursor.execute("SELECT * FROM entrepreneur_profile WHERE email = %s", (email,))
        profile = cursor.fetchone() or {}

        # Fetch pitch content
        cursor.execute("SELECT * FROM pitch_content WHERE email = %s", (email,))
        pitch = cursor.fetchone() or {}

        cursor.close()

        # Prepare structured data for Gemini
        entrepreneur_data = {
            "entrepreneur_profile": {
                "startup_name": profile.get("startup_name"),
                "bio": profile.get("bio"),
                "location": profile.get("location"),
                "industry": profile.get("industry"),
                "stage": profile.get("stage"),
                "funding_required": profile.get("funding_required"),
                "team_size": profile.get("team_size"),
                "founded_year": profile.get("founded_year"),
            },
            "pitch_deck_summary": {
                "problem": pitch.get("problem"),
                "solution": pitch.get("solution"),
                "market": pitch.get("market"),
                "business_model": pitch.get("business_model"),
                "traction": pitch.get("traction"),
                "team_background": pitch.get("team"),
                "the_ask": pitch.get("the_ask"),
            }
        }
        return entrepreneur_data
    except Exception as e:
        logger.error(f"❌ Error fetching entrepreneur data for {email}: {e}")
        return {}

def compute_and_save_entrepreneur_profile_score(email: str, db_connection) -> bool:
    """
    Call Gemini to get a profile score for the entrepreneur and save it to the database.
    
    Returns:
        bool: True if scoring and save was successful, False otherwise.
    """
    try:
        logger.info(f"🔄 Starting entrepreneur profile scoring for {email}")
        
        entrepreneur_data = get_entrepreneur_data_for_scoring(email, db_connection)
        
        # Check if we have profile data to score
        profile_data = entrepreneur_data.get("entrepreneur_profile", {})
        if not any([profile_data.get("startup_name"), profile_data.get("bio"), profile_data.get("industry")]):
            logger.warning(f"⚠️ Insufficient profile data for {email}, skipping scoring.")
            return False

        entrepreneur_json = json.dumps(entrepreneur_data, indent=2, default=str)
        logger.debug(f"📊 Prepared data for scoring: {entrepreneur_json[:200]}...")

        prompt_template = """You are an experienced startup investor and accelerator evaluator.

Your task is to calculate an Entrepreneur Profile Score between 0 and 95. This score represents the startup's readiness and appeal to investors.

Evaluate the entrepreneur's profile and pitch based on the following criteria:

1.  **Profile & Pitch Completeness (0–15)**: How well-documented is the profile and pitch summary?
2.  **Problem & Solution Clarity (0–20)**: Is the problem significant and the solution compelling and clear?
3.  **Market Opportunity (0–15)**: Is the market size and potential clearly articulated and attractive?
4.  **Traction & Progress (0–15)**: Is there evidence of early traction, MVP, or user validation?
5.  **Team Strength (0–15)**: Does the team background inspire confidence?
6.  **Investment Appeal (The Ask) (0–10)**: Is the funding ask clear and justified?
7.  **Overall Cohesion (0–5)**: How well do all the pieces fit together into a coherent story?

**Rules:**
- Never give a score above 95.
- Return ONLY valid JSON, no markdown, no extra text.
- Be strict and realistic. A great idea without execution details should not score high.

**Output format (valid JSON only):**
{
  "profile_score": <number 0-95>,
  "confidence": "High|Medium|Low",
  "score_breakdown": {
    "completeness": <0-15>,
    "problem_solution": <0-20>,
    "market_opportunity": <0-15>,
    "traction": <0-15>,
    "team_strength": <0-15>,
    "investment_appeal": <0-10>,
    "cohesion": <0-5>
  },
  "summary": "A short, constructive summary for the entrepreneur explaining the score."
}"""
        
        prompt = f"{prompt_template}\n\nEntrepreneur data:\n{entrepreneur_json}"
        logger.info(f"🤖 Sending prompt to Gemini for {email}...")

        client = get_gemini_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=4048,
                temperature=0.1,
                response_mime_type="application/json",
            )
        )

        result_text = response.text.strip()
        logger.debug(f"📤 Raw Gemini response: {result_text[:300]}...")
        logger.debug(f"📊 Response length: {len(result_text)} characters")

        # Strip markdown if Gemini accidentally adds it
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()
        
        # Verify JSON is complete before parsing
        if not result_text.endswith("}"):
            logger.error(f"❌ Incomplete JSON response for {email}")
            logger.error(f"   Response does not end with closing brace: {result_text[-50:]}")
            return False

        # Parse JSON response
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response for {email}: {e}")
            logger.error(f"   Response was: {result_text}")
            logger.error(f"   Response length: {len(result_text)} chars")
            return False

        logger.debug(f"✅ Parsed result: {result}")

        # Extract score data
        score = result.get("profile_score")
        breakdown = json.dumps(result.get("score_breakdown", {}))
        summary = result.get("summary", "")
        confidence = result.get("confidence", "Medium")

        # Validate score
        if score is None:
            logger.warning(f"⚠️ Gemini response for {email} did not contain a profile_score.")
            return False
        
        if not isinstance(score, (int, float)) or score < 0 or score > 95:
            logger.warning(f"⚠️ Invalid score value: {score} for {email}")
            return False

        logger.info(f"💾 Saving score {score} for {email}")
        cursor = db_connection.cursor()
        cursor.execute("""
            UPDATE entrepreneur_profile
            SET profile_score = %s,
                profile_score_breakdown = %s,
                profile_score_summary = %s
            WHERE email = %s
        """, (int(score), breakdown, summary, email))
        db_connection.commit()
        cursor.close()
        
        logger.info(f"✅ Entrepreneur profile score saved for {email}: {score}")
        return True

    except Exception as e:
        logger.error(f"❌ Error in Gemini scoring for entrepreneur {email}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
