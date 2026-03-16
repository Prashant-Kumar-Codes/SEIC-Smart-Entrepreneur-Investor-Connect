import json
import numpy as np
from datetime import datetime
import threading
from app.routes.extensions import *
from psycopg2.extras import RealDictCursor

try:
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"[CRITICAL] sentence_transformers not installed. Install with: pip install sentence-transformers")

# ── Sentence-Transformers model (singleton) ────────────────────
_model = None

def get_embedding_model():
    """Load all-MiniLM-L6-v2 once, reuse globally."""
    global _model
    if _model is None:
        try:
            print("[INFO] Loading embedding model: all-MiniLM-L6-v2 (this may take 30-60 seconds on first load)...")
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            print("[OK] Embedding model loaded: all-MiniLM-L6-v2")
        except Exception as e:
            print(f"[CRITICAL] Failed to load embedding model: {e}")
            raise RuntimeError(f"Failed to load embedding model: {e}") from e
    return _model

# Preload the model synchronously when the module is imported.
# This ensures PyTorch CUDA inits sequentially during Flask boot,
# avoiding Windows watchdog false-positive restarts from background threads!
get_embedding_model()

 
# ── Generate normalized embedding ─────────────────────────────
def generate_embedding(text: str) -> list:
    """
    Encode text → L2-normalized float32 vector (384-dim).
    Normalized → cosine similarity == dot product (faster).
    Returns plain Python list for JSON storage.
    """
    model = get_embedding_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


# ── Build text blobs for embedding ────────────────────────────
def build_entrepreneur_text(profile: dict, pitch: dict) -> str:
    """
    Concatenate all meaningful entrepreneur / pitch fields into
    one rich string for embedding. The richer the text, the
    better the semantic match.
    """
    p   = profile or {}
    pc  = pitch   or {}
    parts = [
        p.get('startup_name', ''),
        p.get('industry', ''),
        p.get('stage', ''),
        p.get('bio', ''),
        p.get('focus_areas', ''),
        p.get('use_of_funds', ''),
        p.get('location', ''),
        pc.get('problem', ''),
        pc.get('solution', ''),
        pc.get('market', ''),
        pc.get('business_model', ''),
        pc.get('traction', ''),
        pc.get('team', ''),
        pc.get('the_ask', ''),
    ]
    return ' '.join(x for x in parts if x).strip()


def build_investor_text(profile: dict, portfolio: dict) -> str:
    """
    Concatenate investor profile + investment profile (portfolio)
    into one rich string for embedding.
    """
    p  = profile   or {}
    pp = portfolio or {}
    parts = [
        p.get('firm_name', ''),
        p.get('full_name', ''),
        p.get('investor_type', ''),
        p.get('investment_focus', ''),
        p.get('preferred_sectors', ''),
        p.get('geography', ''),
        p.get('bio', ''),
        pp.get('investment_thesis', ''),
        pp.get('deal_criteria', ''),
        pp.get('sector_expertise', ''),
        pp.get('value_add', ''),
        pp.get('portfolio_highlights', ''),
    ]
    return ' '.join(x for x in parts if x).strip()


# ── Store embedding in DB ──────────────────────────────────────
def store_embedding(email: str, role: str, text: str, db_connection) -> bool:
    """
    Generate embedding from text and upsert into user_embeddings.
    role: 'entrepreneur' | 'investor'
    Returns True on success.
    """
    if not text or not text.strip():
        print(f"⚠️ Empty text for embedding ({email}), skipping.")
        return False
    try:
        embedding = generate_embedding(text)
        embedding_json = json.dumps(embedding)

        cursor = db_connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO user_embeddings (email, role, embedding, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (email) DO UPDATE SET
                    embedding  = EXCLUDED.embedding,
                    updated_at = NOW()
            """, (email, role, embedding_json))
            db_connection.commit()
            cursor.close()
            print(f"✅ Embedding stored for {role} {email} ({len(embedding)} dims)")
            return True
        except Exception as db_err:
            if "user_embeddings" in str(db_err):
                print(f"❌ Table 'user_embeddings' does not exist in database. Please run migrations.")
                raise RuntimeError("Missing table: user_embeddings") from db_err
            raise
    except Exception as e:
        print(f"❌ store_embedding error ({email}): {e}")
        import traceback; traceback.print_exc()
        return False


# ── Load embedding from DB ─────────────────────────────────────
def load_embedding(email: str, cursor) -> np.ndarray | None:
    """Load embedding vector from DB, return as NumPy array."""
    cursor.execute(
        "SELECT embedding FROM user_embeddings WHERE email = %s",
        (email,)
    )
    row = cursor.fetchone()
    if not row or not row.get('embedding'):
        return None
    try:
        return np.array(json.loads(row['embedding']), dtype=np.float32)
    except Exception as e:
        print(f"⚠️ load_embedding parse error ({email}): {e}")
        return None


# ── Scoring helpers ────────────────────────────────────────────
def cosine_score(a: np.ndarray, b: np.ndarray) -> float:
    """
    Both vectors are already L2-normalized → dot product = cosine similarity.
    Clamped to [0, 1].
    """
    if a is None or b is None:
        return 0.0
    return float(max(0.0, min(1.0, np.dot(a, b))))


def compute_stage_score(startup_stage: str, investor_stage_pref: str) -> float:
    """
    Score how well startup stage matches investor preference.
    1.0 = exact match, 0.6 = adjacent stage, 0.0 = no match.
    """
    if not startup_stage or not investor_stage_pref:
        return 0.5  # unknown → neutral

    # Normalise
    s = startup_stage.lower().replace('-', '').replace(' ', '')
    p = investor_stage_pref.lower().replace('-', '').replace(' ', '')

    stage_order = ['idea', 'preseed', 'seed', 'seriesa', 'seriesb', 'growth']

    def idx(stage_str):
        for i, st in enumerate(stage_order):
            if st in stage_str or stage_str in st:
                return i
        return -1

    if 'all' in p:       return 1.0        # investor takes all stages
    if s == p:           return 1.0        # exact
    si, pi = idx(s), idx(p)
    if si == -1 or pi == -1: return 0.3   # unknown stage
    if abs(si - pi) == 1:    return 0.6   # adjacent (e.g. seed vs pre-seed)
    if abs(si - pi) == 2:    return 0.3   # 2 apart
    return 0.0


def compute_funding_score(
    funding_amount: float,
    inv_min: float,
    inv_max: float
) -> float:
    """
    Score funding alignment.
    1.0 = within investor ticket range
    0.5 = within 2x over/under
    0.0 = far out of range
    """
    if not funding_amount:
        return 0.3    # unknown → mildly penalise
    if not inv_min and not inv_max:
        return 0.5    # investor has no preference set
    lo = float(inv_min or 0)
    hi = float(inv_max or float('inf'))
    fa = float(funding_amount)

    if lo <= fa <= hi:
        return 1.0
    # Within 2x of range
    if fa < lo and lo / fa <= 2:
        return 0.5
    if fa > hi and fa / hi <= 2:
        return 0.5
    return 0.0


def compute_engagement_score(profile_views: int, max_views: int = 500) -> float:
    """Normalise profile views to [0, 1]. Cap at max_views."""
    if not profile_views or max_views == 0:
        return 0.0
    return min(float(profile_views) / max_views, 1.0)


# ── CORE: Compute matches for ONE investor ─────────────────────
def compute_matches_for_investor(investor_email: str, db_connection) -> int:
    """
    Find top startups for a given investor.
    Writes results to ai_match_cache.
    Returns count of matches written.

    Hybrid score weights:
        60% semantic (vector)
        20% stage alignment
        10% funding alignment
        10% engagement (views)
    """
    try:
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)

        # ── Load investor embedding ────────────────────────────────
        inv_vec = load_embedding(investor_email, cursor)
        if inv_vec is None:
            print(f"⚠️ No embedding for investor {investor_email}. Skipping.")
            cursor.close()
            return 0

        # ── Load investor preferences for hard filters ────────────
        cursor.execute("""
            SELECT preferred_sectors, investment_stage,
                   min_ticket_size, max_ticket_size
            FROM investor_portfolio_profile 
            WHERE email = %s
        """, (investor_email,))
        inv_prefs = cursor.fetchone() or {}
        # Some deployments store ticket-size prefs in a separate table
        # `investor_portfolio_profile`. If min/max are missing above,
        # try fetching from that table as a fallback to avoid SQL errors
        if not inv_prefs.get('min_ticket_size') and not inv_prefs.get('max_ticket_size'):
            try:
                cursor.execute(
                    "SELECT min_ticket_size, max_ticket_size FROM investor_portfolio_profile WHERE email = %s",
                    (investor_email,)
                )
                port_row = cursor.fetchone() or {}
                # merge into inv_prefs so later code can read the keys transparently
                if port_row:
                    inv_prefs['min_ticket_size'] = port_row.get('min_ticket_size')
                    inv_prefs['max_ticket_size'] = port_row.get('max_ticket_size')
            except Exception:
                # non-fatal; continue using whatever keys exist
                pass

        # ── Hard SQL filter: narrow candidates ────────────────────
        # Dynamically build query — filters are optional
        where_parts = ["ld.role = 'entrepreneur'",
                       "ue.role = 'entrepreneur'",
                       "ue.embedding IS NOT NULL"]
        params = []

        # Stage filter (only if investor has a preference)
        inv_stage = (inv_prefs.get('investment_stage') or '').strip()
        if inv_stage and 'all' not in inv_stage.lower():
            # Accept exact stage OR adjacent stage for wider recall
            stage_variants = _get_stage_variants(inv_stage)
            if stage_variants:
                placeholders = ','.join(['%s'] * len(stage_variants))
                where_parts.append(f"(ep.stage IN ({placeholders}) OR ep.stage IS NULL)")
                params.extend(stage_variants)

        # Max ticket filter (investor won't exceed max)
        inv_max = inv_prefs.get('max_ticket_size')
        if inv_max:
            where_parts.append("(ep.funding_amount IS NULL OR ep.funding_amount <= %s)")
            params.append(float(inv_max) * 2)   # 2x buffer for flexibility

        query = f"""
            SELECT
                ep.email,
                ep.startup_name,
                ep.industry,
                ep.stage,
                ep.funding_amount,
                ep.funding_currency,
                ep.location,
                ep.profile_image_url,
                ep.profile_views,
                ep.bio,
                ep.profile_score,
                ld.username,
                ue.embedding
            FROM login_data ld
            JOIN entrepreneur_profile ep  ON ld.email = ep.email
            JOIN user_embeddings ue       ON ld.email = ue.email
            WHERE {' AND '.join(where_parts)}
            LIMIT 2000
        """
        cursor.execute(query, params)
        candidates = cursor.fetchall()
        print(f"🔍 Investor {investor_email}: {len(candidates)} candidates after hard filter")

        if not candidates:
            cursor.close()
            return 0

        # ── Score each candidate ───────────────────────────────────
        results = []
        max_views = max((c.get('profile_views') or 0 for c in candidates), default=1) or 1

        for startup in candidates:
            try:
                raw_emb = startup.pop('embedding', None)
                if not raw_emb:
                    continue
                ent_vec = np.array(json.loads(raw_emb), dtype=np.float32)

                v_score   = cosine_score(inv_vec, ent_vec)
                s_score   = compute_stage_score(
                                startup.get('stage', ''), inv_stage)
                f_score   = compute_funding_score(
                                startup.get('funding_amount'),
                                inv_prefs.get('min_ticket_size'),
                                inv_prefs.get('max_ticket_size'))
                e_score   = compute_engagement_score(
                                startup.get('profile_views', 0), max_views)

                final = (
                    0.60 * v_score +
                    0.20 * s_score +
                    0.10 * f_score +
                    0.10 * e_score
                )

                if final >= 0.35:   # minimum threshold for cache
                    results.append({**startup, 'score': final})

            except Exception as ex:
                print(f"⚠️ Scoring error for {startup.get('email')}: {ex}")
                continue

        # ── Sort descending ────────────────────────────────────────
        results.sort(key=lambda x: x['score'], reverse=True)
        top_matches = results[:20]

        # ── Write to cache ─────────────────────────────────────────
        # Delete stale cache first
        cursor.execute("""
            DELETE FROM ai_match_cache
            WHERE investor_email = %s AND direction = 'investor_to_entrepreneur'
        """, (investor_email,))

        written = 0
        for match in top_matches:
            try:
                cursor.execute("""
                    INSERT INTO ai_match_cache
                        (investor_email, entrepreneur_email, score, direction, computed_at)
                    VALUES (%s, %s, %s, 'investor_to_entrepreneur', NOW())
                """, (investor_email, match['email'], round(match['score'], 4)))
                written += 1
            except Exception as ex:
                print(f"⚠️ Cache insert error: {ex}")

        db_connection.commit()
        cursor.close()
        top_score = top_matches[0]['score'] if top_matches else 0
        print(f"✅ Investor {investor_email}: {written} matches cached (top score: {top_score:.3f})")
        return written
        
    except Exception as e:
        print(f"❌ compute_matches_for_investor error: {e}")
        import traceback; traceback.print_exc()
        try:
            cursor.close()
        except:
            pass
        return 0


# ── CORE: Compute matches for ONE entrepreneur ─────────────────
def compute_matches_for_entrepreneur(entrepreneur_email: str, db_connection) -> int:
    """
    Find top investors for a given entrepreneur.
    Writes results to ai_match_cache.

    Hybrid score weights:
        60% semantic (vector)
        20% stage alignment
        10% funding alignment
        10% investor engagement proxy (total_investments)
    """
    try:
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)

        # ── Load entrepreneur embedding ────────────────────────────
        ent_vec = load_embedding(entrepreneur_email, cursor)
        if ent_vec is None:
            print(f"⚠️ No embedding for entrepreneur {entrepreneur_email}. Skipping.")
            cursor.close()
            return 0

        # ── Load entrepreneur profile for filter info ──────────────
        cursor.execute("""
            SELECT stage, funding_amount, funding_currency,
                   industry, location
            FROM entrepreneur_profile
            WHERE email = %s
        """, (entrepreneur_email,))
        ent_prefs = cursor.fetchone() or {}

        # ── Hard filter: investors with embeddings ─────────────────
        cursor.execute("""
            SELECT
                ip.email,
                ip.full_name,
                ip.firm_name,
                ip.investor_type,
                ip.investment_focus,
                ip.preferred_sectors,
                -- ticket-size and stage prefs live in investor_portfolio_profile
                ipp.investment_stage AS investment_stage,
                ipp.min_ticket_size     AS min_ticket_size,
                ipp.max_ticket_size     AS max_ticket_size,
                ip.geography,
                ip.profile_image_url,
                ip.total_investments,
                ip.is_verified_investor,
                ip.is_premium,
                ld.username,
                ue.embedding
            FROM investor_profiles ip
            LEFT JOIN investor_portfolio_profile ipp ON ip.email = ipp.email
            JOIN login_data ld      ON ip.email = ld.email
            JOIN user_embeddings ue ON ip.email = ue.email
            WHERE ld.role = 'investor'
              AND ue.role = 'investor'
              AND ue.embedding IS NOT NULL
            LIMIT 2000
        """)
        candidates = cursor.fetchall()
        print(f"🔍 Entrepreneur {entrepreneur_email}: {len(candidates)} investor candidates")

        if not candidates:
            cursor.close()
            return 0

        results = []
        ent_stage   = ent_prefs.get('stage', '')
        ent_funding = ent_prefs.get('funding_amount')
        max_investments = max((c.get('total_investments') or 0 for c in candidates), default=1) or 1

        for investor in candidates:
            try:
                raw_emb = investor.pop('embedding', None)
                if not raw_emb:
                    continue
                inv_vec = np.array(json.loads(raw_emb), dtype=np.float32)

                v_score = cosine_score(ent_vec, inv_vec)
                s_score = compute_stage_score(
                              ent_stage,
                              investor.get('investment_stage', ''))
                f_score = compute_funding_score(
                              ent_funding,
                              investor.get('min_ticket_size'),
                              investor.get('max_ticket_size'))
                e_score = compute_engagement_score(
                              investor.get('total_investments', 0),
                              max_investments)

                final = (
                    0.60 * v_score +
                    0.20 * s_score +
                    0.10 * f_score +
                    0.10 * e_score
                )

                if final >= 0.35:
                    results.append({**investor, 'score': final})

            except Exception as ex:
                print(f"⚠️ Scoring error for investor {investor.get('email')}: {ex}")
                continue

        results.sort(key=lambda x: x['score'], reverse=True)
        top_matches = results[:20]

        # ── Write to cache ─────────────────────────────────────────
        cursor.execute("""
            DELETE FROM ai_match_cache
            WHERE entrepreneur_email = %s AND direction = 'entrepreneur_to_investor'
        """, (entrepreneur_email,))

        written = 0
        for match in top_matches:
            try:
                cursor.execute("""
                    INSERT INTO ai_match_cache
                        (investor_email, entrepreneur_email, score, direction, computed_at)
                    VALUES (%s, %s, %s, 'entrepreneur_to_investor', NOW())
                """, (match['email'], entrepreneur_email, round(match['score'], 4)))
                written += 1
            except Exception as ex:
                print(f"⚠️ Cache insert error: {ex}")

        db_connection.commit()
        cursor.close()
        print(f"✅ Entrepreneur {entrepreneur_email}: {written} investor matches cached")
        return written
        
    except Exception as e:
        print(f"❌ compute_matches_for_entrepreneur error: {e}")
        import traceback; traceback.print_exc()
        try:
            cursor.close()
        except:
            pass
        return 0


# ── Serve cached matches ───────────────────────────────────────
def get_cached_investor_matches(investor_email: str, db_connection, limit: int = 20) -> list:
    """
    Return cached startup matches for an investor, enriched with full profile data.
    If cache is empty or stale (>24h), trigger recomputation first.
    """
    try:
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)

        # Check if cache exists and is fresh
        cursor.execute("""
            SELECT COUNT(*) AS cnt,
                   MAX(computed_at) AS last_computed
            FROM ai_match_cache
            WHERE investor_email = %s
              AND direction = 'investor_to_entrepreneur'
        """, (investor_email,))
        cache_info = cursor.fetchone()

        needs_recompute = (
            not cache_info or
            cache_info['cnt'] == 0 or
            cache_info['last_computed'] is None or
            (datetime.now() - cache_info['last_computed']).total_seconds() > 86400  # 24h
        )

        if needs_recompute:
            cursor.close()
            print(f"🔄 Cache miss/stale for investor {investor_email} — recomputing…")
            compute_matches_for_investor(investor_email, db_connection)
            cursor = db_connection.cursor(cursor_factory=RealDictCursor)

        # Fetch cached matches + full startup profile in one join
        cursor.execute("""
            SELECT
                amc.score,
                amc.computed_at,
                ep.email          AS entrepreneur_email,
                ep.startup_name,
                ep.industry,
                ep.stage,
                ep.funding_amount,
                ep.funding_currency,
                ep.funding_required,
                ep.location,
                ep.profile_image_url,
                ep.profile_views,
                ep.bio,
                ep.founded_year,
                ep.team_size,
                ep.profile_score,
                ep.is_verified_profile,
                ld.username
            FROM ai_match_cache amc
            JOIN entrepreneur_profile ep ON amc.entrepreneur_email = ep.email
            JOIN login_data ld           ON ep.email = ld.email
            WHERE amc.investor_email = %s
              AND amc.direction = 'investor_to_entrepreneur'
            ORDER BY amc.score DESC
            LIMIT %s
        """, (investor_email, limit))
        matches = cursor.fetchall()
        cursor.close()
        return matches
        
    except Exception as e:
        print(f"❌ get_cached_investor_matches error: {e}")
        import traceback; traceback.print_exc()
        try:
            cursor.close()
        except:
            pass
        return []


def get_cached_entrepreneur_matches(entrepreneur_email: str, db_connection, limit: int = 20) -> list:
    """
    Return cached investor matches for an entrepreneur.
    Auto-recomputes if cache is empty or stale (>24h).
    """
    try:
        cursor = db_connection.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT COUNT(*) AS cnt,
                   MAX(computed_at) AS last_computed
            FROM ai_match_cache
            WHERE entrepreneur_email = %s
              AND direction = 'entrepreneur_to_investor'
        """, (entrepreneur_email,))
        cache_info = cursor.fetchone()

        needs_recompute = (
            not cache_info or
            cache_info['cnt'] == 0 or
            cache_info['last_computed'] is None or
            (datetime.now() - cache_info['last_computed']).total_seconds() > 86400
        )

        if needs_recompute:
            cursor.close()
            print(f"🔄 Cache miss/stale for entrepreneur {entrepreneur_email} — recomputing…")
            compute_matches_for_entrepreneur(entrepreneur_email, db_connection)
            cursor = db_connection.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                amc.score,
                amc.computed_at,
                ip.email          AS investor_email,
                ip.full_name,
                ip.firm_name,
                ip.investor_type,
                ip.investment_focus,
                ip.preferred_sectors,
                -- ticket preferences from portfolio table
                ipp.investment_stage AS investment_stage,
                ipp.min_ticket_size   AS min_ticket_size,
                ipp.max_ticket_size   AS max_ticket_size,
                ip.geography,
                ip.profile_image_url,
                ip.total_investments,
                ip.is_verified_investor,
                ip.is_premium,
                ip.bio,
                ld.username
            FROM ai_match_cache amc
            JOIN investor_profiles ip ON amc.investor_email = ip.email
            LEFT JOIN investor_portfolio_profile ipp ON ip.email = ipp.email
            JOIN login_data ld        ON ip.email = ld.email
            WHERE amc.entrepreneur_email = %s
              AND amc.direction = 'entrepreneur_to_investor'
            ORDER BY amc.score DESC
            LIMIT %s
        """, (entrepreneur_email, limit))
        matches = cursor.fetchall()
        cursor.close()
        return matches
        
    except Exception as e:
        print(f"❌ get_cached_entrepreneur_matches error: {e}")
        import traceback; traceback.print_exc()
        try:
            cursor.close()
        except:
            pass
        return []
    
    except Exception as e:
        print(f"❌ get_cached_entrepreneur_matches error: {e}")
        import traceback; traceback.print_exc()
        try:
            cursor.close()
        except:
            pass
        return []


# ── Trigger functions (call from save routes) ──────────────────
def trigger_on_pitch_save(entrepreneur_email: str, profile: dict, pitch: dict, db_connection):
    """
    Called every time an entrepreneur saves their pitch.
    1. Regenerate entrepreneur embedding
    2. Recompute their investor matches (entrepreneur→investor direction)
    3. Invalidate all investor→entrepreneur caches that included this startup
       so investor matches refresh on next load (lazy)
    """
    print(f"⚡ Pitch saved: regenerating embedding + matches for {entrepreneur_email}")

    text = build_entrepreneur_text(profile, pitch)
    if not text:
        print(f"⚠️ No text to embed for {entrepreneur_email}")
        return

    store_embedding(entrepreneur_email, 'entrepreneur', text, db_connection)

    # Recompute entrepreneur→investor matches
    compute_matches_for_entrepreneur(entrepreneur_email, db_connection)

    # Lazy invalidate: delete all investor→entrepreneur cache rows for this startup
    # Investors will recompute on next page load
    try:
        cursor = db_connection.cursor()
        cursor.execute("""
            DELETE FROM ai_match_cache
            WHERE entrepreneur_email = %s
              AND direction = 'investor_to_entrepreneur'
        """, (entrepreneur_email,))
        db_connection.commit()
        cursor.close()
    except Exception as e:
        print(f"⚠️ Cache invalidation error: {e}")


def trigger_on_investor_portfolio_save(
    investor_email: str,
    investor_profile: dict,
    investor_pitch_profile: dict,
    db_connection
):
    """
    Called every time an investor saves their portfolio/profile.
    1. Regenerate investor embedding
    2. Recompute investor→entrepreneur matches
    """
    print(f"⚡ Portfolio saved: regenerating embedding + matches for {investor_email}")

    text = build_investor_text(investor_profile, investor_pitch_profile)
    if not text:
        print(f"⚠️ No text to embed for investor {investor_email}")
        return

    store_embedding(investor_email, 'investor', text, db_connection)
    compute_matches_for_investor(investor_email, db_connection)


def async_trigger_on_investor_portfolio_save(
    investor_email: str,
    investor_profile: dict,
    investor_portfolio: dict
):
    """
    Spawn background thread to regenerate investor embeddings.
    The worker will open its own DB connection so it can run long after the
    request has completed.
    Returns immediately without blocking the request.
    """
    print(f"🔄 [ASYNC] Investor embedding task queued for {investor_email}")
    thread = threading.Thread(
        target=_async_trigger_on_investor_portfolio_save_bg,
        args=(investor_email, investor_profile, investor_portfolio),
        daemon=True
    )
    thread.start()


def _async_trigger_on_investor_portfolio_save_bg(
    investor_email: str,
    investor_profile: dict,
    investor_portfolio: dict
):
    """
    Background thread target: Run embedding generation asynchronously.
    Prevents watchdog from restarting when sentence_transformers loads.
    Opens its own DB connection and closes it when finished.
    """
    from ..routes.extensions import get_db_connection

    db_connection = get_db_connection()
    try:
        trigger_on_investor_portfolio_save(
            investor_email, investor_profile, investor_portfolio, db_connection)
        print(f"✅ Investor embedding completed for {investor_email}")
    except Exception as e:
        print(f"❌ Background investor embedding error for {investor_email}: {e}")
    finally:
        try:
            db_connection.close()
        except Exception:
            pass


# ── ASYNC Background task wrappers (prevent watchdog restart) ──
def _async_trigger_on_pitch_save_bg(entrepreneur_email: str, profile: dict, pitch: dict):
    """
    Background thread target: Run embedding generation asynchronously.
    Prevents watchdog from restarting when sentence_transformers loads.
    Opens a new DB connection for the duration of the operation.
    """
    from ..routes.extensions import get_db_connection

    db_connection = get_db_connection()
    try:
        trigger_on_pitch_save(entrepreneur_email, profile, pitch, db_connection)
        print(f"✅ Pitch embedding completed for {entrepreneur_email}")
    except Exception as e:
        print(f"❌ Background embedding error for {entrepreneur_email}: {e}")
    finally:
        try:
            db_connection.close()
        except Exception:
            pass


# ── Async helpers revised to avoid using request-scoped connection ──
# previously the thread was passed the Flask request's db_connection and
# would crash silently once the request finished.  Instead the background
# worker now opens its own connection and closes it when done.

def async_trigger_on_pitch_save(entrepreneur_email: str, profile: dict, pitch: dict):
    """
    Spawn background thread to regenerate entrepreneur embeddings.
    The thread obtains its own fresh DB connection so we never reuse the
    request's connection (which is closed when the response is sent).
    Returns immediately without blocking the request.
    """
    print(f"🔄 [ASYNC] Embedding task queued for {entrepreneur_email}")
    thread = threading.Thread(
        target=_async_trigger_on_pitch_save_bg,
        args=(entrepreneur_email, profile, pitch),
        daemon=True
    )
    thread.start()


# ── Score band labels ─────────────────────────────────────────
def score_to_label(score: float) -> dict:
    """Return a human-readable compatibility label + colour."""
    if score >= 0.80: return {'label': 'Excellent Match',   'color': '#10b981', 'pct': int(score*100)}
    if score >= 0.65: return {'label': 'Strong Match',      'color': '#3b82f6', 'pct': int(score*100)}
    if score >= 0.50: return {'label': 'Good Match',        'color': '#f59e0b', 'pct': int(score*100)}
    if score >= 0.40: return {'label': 'Moderate Match',    'color': '#6b7280', 'pct': int(score*100)}
    return                    {'label': 'Weak Match',        'color': '#d1d5db', 'pct': int(score*100)}


# ── Internal helper ────────────────────────────────────────────
def _get_stage_variants(stage_pref: str) -> list:
    """Expand 'Seed' → ['seed','pre-seed'] for SQL IN clause."""
    stage_map = {
        'pre-seed'   : ['pre-seed', 'preseed', 'idea'],
        'seed'       : ['seed', 'pre-seed'],
        'series a'   : ['series-a', 'series a', 'seed'],
        'series b'   : ['series-b', 'series b', 'series-a'],
        'growth'     : ['growth', 'series-b', 'series b'],
        'all stages' : [],   # handled upstream
    }
    normalised = stage_pref.lower().strip()
    for key, variants in stage_map.items():
        if key in normalised or normalised in key:
            return variants if variants else []
    return [stage_pref]  # fallback: exact match only