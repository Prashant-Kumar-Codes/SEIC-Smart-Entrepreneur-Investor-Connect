from sentence_transformers import SentenceTransformer
import numpy as np
import json
from app.routes.extensions import *

#from app.config.config import get_db_connection  # Adjust import if needed

def get_model():
    # Singleton pattern for model loading
    if not hasattr(get_model, "model"):
        get_model.model = SentenceTransformer("all-MiniLM-L6-v2")
        print('embedding model is loaded')
    print('embedding model is used')
    return get_model.model

def generate_embedding(text):
    if not text or text.strip() == "":
        return None
    model = get_model()
    embedding = model.encode(text)
    return embedding.tolist()

def save_entrepreneur_embedding(email, profile, pitch):
    try:
        combined_text = f"""
        Name: {profile.get('name','')}
        Startup: {profile.get('startup_name','')}
        Industry: {profile.get('industry','')}
        Stage: {profile.get('stage','')}
        Problem: {pitch.get('problem','')}
        Solution: {pitch.get('solution','')}
        Market: {pitch.get('market','')}
        Business Model: {pitch.get('business_model','')}
        Traction: {pitch.get('traction','')}
        """
        print(f"[DEBUG] PROFILE: {profile}")
        print(f"[DEBUG] PITCH: {pitch}")
        embedding = generate_embedding(combined_text)
        if not embedding:
            print("⚠️ Empty embedding")
            return
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_embeddings (email, role, embedding, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (email) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
        """, (email, 'entrepreneur', json.dumps(embedding)))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Embedding saved for {email} (entrepreneur)")
    except Exception as e:
        print(f"❌ Embedding error: {e}")

def save_investor_embedding(email, profile):
    try:
        combined_text = f"""
        Name: {profile.get('name','')}
        Firm: {profile.get('firm','')}
        Focus: {profile.get('focus','')}
        Stage: {profile.get('stage','')}
        Investment Thesis: {profile.get('investment_thesis','')}
        """
        print(f"[DEBUG] INVESTOR PROFILE: {profile}")
        embedding = generate_embedding(combined_text)
        if not embedding:
            print("⚠️ Empty embedding")
            return
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_embeddings (email, role, embedding, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (email) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
        """, (email, 'investor', json.dumps(embedding)))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Investor embedding saved for {email}")
    except Exception as e:
        print(f"❌ Investor embedding error: {e}")
