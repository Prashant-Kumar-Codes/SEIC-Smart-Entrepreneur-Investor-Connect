-- ═════════════════════════════════════════════════════════════════════════════
-- SEIC DATABASE SCHEMA - PostgreSQL VERSION
-- Smart Entrepreneur-Investor-Connect Platform
-- Convert from MySQL to PostgreSQL
-- ═════════════════════════════════════════════════════════════════════════════

-- Create database
CREATE DATABASE seic_db;
-- Then connect to seic_db and run the rest of this file

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. LOGIN_DATA - Users authentication
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS login_data (
    id                  SERIAL PRIMARY KEY,
    email               VARCHAR(255) PRIMARY KEY UNIQUE,
    username            VARCHAR(50) NOT NULL,
    age                 SMALLINT NOT NULL,
    role                VARCHAR(20) NOT NULL,
    gender              VARCHAR(10) NOT NULL,
    password            VARCHAR(255) NOT NULL,
    otp                 VARCHAR(6),
    otp_created_at      TIMESTAMP,
    is_verified         BOOLEAN DEFAULT FALSE,
    authorized          VARCHAR(100),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_role CHECK (role IN ('entrepreneur', 'investor', 'admin'))
);
CREATE INDEX idx_login_email ON login_data(email);
CREATE INDEX idx_login_role ON login_data(role);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. ENTREPRENEUR_PROFILE - Extended entrepreneur profile
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entrepreneur_profile (
    email               VARCHAR(255) PRIMARY KEY,
    startup_name        VARCHAR(150) NOT NULL,
    bio                 TEXT,
    industry            VARCHAR(100),
    location            VARCHAR(100),
    website_url         VARCHAR(255),
    profile_image_url   VARCHAR(500),
    linkedin_url        VARCHAR(255),
    twitter_url         VARCHAR(255),
    stage               VARCHAR(30),
    founded_year        INTEGER,
    team_size           VARCHAR(30),
    focus_areas         TEXT,
    funding_amount      DECIMAL(15,2),
    funding_currency    VARCHAR(10) DEFAULT 'INR',
    funding_required    VARCHAR(50),
    use_of_funds        TEXT,
    funding_progress_pct INTEGER DEFAULT 0,
    profile_views       INTEGER DEFAULT 0,
    investors_connected INTEGER DEFAULT 0,
    total_pitches       INTEGER DEFAULT 0,
    profile_score       FLOAT DEFAULT 0,
    profile_score_breakdown JSONB,
    profile_score_summary TEXT,
    is_premium          BOOLEAN DEFAULT FALSE,
    is_verified_profile BOOLEAN DEFAULT FALSE,
    video_pitch_url     VARCHAR(500),
    demo_url            VARCHAR(500),
    pitch_deck_url      VARCHAR(500),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ep_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_ep_industry ON entrepreneur_profile(industry);
CREATE INDEX idx_ep_stage ON entrepreneur_profile(stage);
CREATE INDEX idx_ep_created ON entrepreneur_profile(created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. PITCH_CONTENT - Pitch deck details
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pitch_content (
    pitch_id            SERIAL PRIMARY KEY,
    email               VARCHAR(255) NOT NULL UNIQUE,
    problem             TEXT,
    solution            TEXT,
    market              TEXT,
    business_model      TEXT,
    traction            TEXT,
    team                TEXT,
    financials          TEXT,
    the_ask             TEXT,
    video_pitch_url     VARCHAR(255),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pc_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_pc_email ON pitch_content(email);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3.5. INVESTOR_PORTFOLIO_PROFILE - Investor portfolio and criteria
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investor_portfolio_profile (
    email                       VARCHAR(255) PRIMARY KEY,
    investment_thesis           TEXT,
    deal_criteria               TEXT,
    portfolio_highlights        TEXT,
    sector_expertise            TEXT,
    dd_framework                TEXT,
    value_add                   TEXT,
    exit_strategy               TEXT,
    co_investment               TEXT,
    preferred_sectors           VARCHAR(255),
    investment_stage            VARCHAR(100),
    min_ticket_size             DECIMAL(15,2),
    max_ticket_size             DECIMAL(15,2),
    available_funds             DECIMAL(15,2) DEFAULT 0,
    investment_utilization_pct  DECIMAL(5,2) DEFAULT 0,
    capital_deployed_pct        DECIMAL(6,4),
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ipp_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_ipp_email ON investor_portfolio_profile(email);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. USER_POSTS - Public posts/feed
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_posts (
    post_id             SERIAL PRIMARY KEY,
    email               VARCHAR(255) NOT NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    industry_tag        VARCHAR(100),
    pitch_deck_url      VARCHAR(500),
    video_url           VARCHAR(500),
    thumbnail_url       VARCHAR(500),
    likes_count         INTEGER DEFAULT 0,
    comments_count      INTEGER DEFAULT 0,
    saves_count         INTEGER DEFAULT 0,
    views_count         INTEGER DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_up_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_up_email ON user_posts(email);
CREATE INDEX idx_up_created ON user_posts(created_at DESC);
CREATE INDEX idx_up_active ON user_posts(is_active);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4.5. PITCH_POSTS - Alias/alternative posts table (if separate from user_posts)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pitch_posts (
    post_id             SERIAL PRIMARY KEY,
    email               VARCHAR(255) NOT NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    industry_tag        VARCHAR(100),
    pitch_deck_url      VARCHAR(500),
    video_url           VARCHAR(500),
    thumbnail_url       VARCHAR(500),
    likes_count         INTEGER DEFAULT 0,
    comments_count      INTEGER DEFAULT 0,
    saves_count         INTEGER DEFAULT 0,
    views_count         INTEGER DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pp_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_pp_email ON pitch_posts(email);
CREATE INDEX idx_pp_created ON pitch_posts(created_at DESC);
CREATE INDEX idx_pp_active ON pitch_posts(is_active);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. INVESTOR_PROFILES - Extended investor profile
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investor_profiles (
    email               VARCHAR(255) PRIMARY KEY,
    full_name           VARCHAR(150),
    firm_name           VARCHAR(150),
    bio                 TEXT,
    investment_focus    VARCHAR(255),
    location            VARCHAR(100),
    website_url         VARCHAR(255),
    profile_image_url   VARCHAR(500),
    linkedin_url        VARCHAR(255),
    twitter_url         VARCHAR(255),
    crunchbase_url      VARCHAR(255),
    geography           VARCHAR(150),
    investor_type       VARCHAR(80),
    current_position    VARCHAR(150),
    years_of_experience INTEGER,
    education           VARCHAR(200),
    previous_roles      TEXT,
    investor_rating     DECIMAL(3,1),
    total_investments   INTEGER DEFAULT 0,
    startups_connected  INTEGER DEFAULT 0,
    profile_views       INTEGER DEFAULT 0,
    preferred_sectors   VARCHAR(255),
    profile_score       SMALLINT,
    investment_stage    VARCHAR(255),
    profile_score_breakdown JSONB,
    profile_score_summary TEXT,
    profile_score_confidence VARCHAR(20),
    is_premium          BOOLEAN DEFAULT FALSE,
    is_verified_investor BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ip_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_ip_geography ON investor_profiles(geography);
CREATE INDEX idx_ip_investor_type ON investor_profiles(investor_type);
CREATE INDEX idx_ip_created ON investor_profiles(created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 13. INVESTOR_PORTFOLIO - Actual investments made
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investor_portfolio (
    investment_id       SERIAL PRIMARY KEY,
    investor_email      VARCHAR(255) NOT NULL,
    startup_name        VARCHAR(255) NOT NULL,
    entrepreneur_email  VARCHAR(255),
    investment_amount   DECIMAL(15,2) NOT NULL,
    equity_percentage   DECIMAL(5,2),
    investment_date     DATE NOT NULL,
    investment_stage    VARCHAR(100),
    sector              VARCHAR(100),
    status              VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'exited', 'written_off')),
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ip_investor FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_ip_entrepreneur FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE SET NULL
);
CREATE INDEX idx_ip_investor ON investor_portfolio(investor_email, investment_date DESC);
CREATE INDEX idx_ip_status ON investor_portfolio(investor_email, status);

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. POST_INTERACTIONS - Likes, saves, views on posts
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS post_interactions (
    interaction_id      SERIAL PRIMARY KEY,
    user_email          VARCHAR(255) NOT NULL,
    post_id             INTEGER NOT NULL,
    interaction_type    VARCHAR(50) NOT NULL CHECK (interaction_type IN ('like', 'save', 'interested', 'view')),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_email, post_id, interaction_type),
    CONSTRAINT fk_pi_user FOREIGN KEY (user_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_pi_post FOREIGN KEY (post_id) REFERENCES pitch_posts(post_id) ON DELETE CASCADE
);
CREATE INDEX idx_pi_user_email ON post_interactions(user_email);
CREATE INDEX idx_pi_post_id ON post_interactions(post_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. POST_COMMENTS - Comments on posts
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS post_comments (
    comment_id          SERIAL PRIMARY KEY,
    post_id             INTEGER NOT NULL,
    email               VARCHAR(255) NOT NULL,
    comment_text        TEXT NOT NULL,
    parent_comment_id   INTEGER,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pcm_post FOREIGN KEY (post_id) REFERENCES pitch_posts(post_id) ON DELETE CASCADE,
    CONSTRAINT fk_pcm_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_pcm_parent FOREIGN KEY (parent_comment_id) REFERENCES post_comments(comment_id) ON DELETE SET NULL
);
CREATE INDEX idx_pcm_post_id ON post_comments(post_id);
CREATE INDEX idx_pcm_email ON post_comments(email);
CREATE INDEX idx_pcm_parent ON post_comments(parent_comment_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 8. SAVED_INVESTORS - Entrepreneurs' saved investors
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saved_investors (
    save_id             SERIAL PRIMARY KEY,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    investor_email      VARCHAR(255) NOT NULL,
    saved_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entrepreneur_email, investor_email),
    CONSTRAINT fk_si_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_si_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_si_entrepreneur ON saved_investors(entrepreneur_email, saved_at DESC);
CREATE INDEX idx_si_investor ON saved_investors(investor_email);

-- ─────────────────────────────────────────────────────────────────────────────
-- 9. SAVED_STARTUPS - Investors' saved startups
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saved_startups (
    save_id             SERIAL PRIMARY KEY,
    investor_email      VARCHAR(255) NOT NULL,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    notes               TEXT,
    saved_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(investor_email, entrepreneur_email),
    CONSTRAINT fk_ss_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_ss_investor ON saved_startups(investor_email, saved_at DESC);
CREATE INDEX idx_ss_entrepreneur ON saved_startups(entrepreneur_email);

-- ─────────────────────────────────────────────────────────────────────────────
-- 10. SAVED_POSTS - Users' saved posts
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saved_posts (
    save_id             SERIAL PRIMARY KEY,
    user_email          VARCHAR(255) NOT NULL,
    post_id             INTEGER NOT NULL,
    saved_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_email, post_id),
    CONSTRAINT fk_sp_user FOREIGN KEY (user_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_sp_post FOREIGN KEY (post_id) REFERENCES pitch_posts(post_id) ON DELETE CASCADE
);
CREATE INDEX idx_sp_user ON saved_posts(user_email, saved_at DESC);
CREATE INDEX idx_sp_post ON saved_posts(post_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 11. CONNECTIONS - Entrepreneur <-> Investor connections
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS connections (
    connection_id       SERIAL PRIMARY KEY,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    investor_email      VARCHAR(255) NOT NULL,
    status              VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'withdrawn')),
    requested_by        VARCHAR(255) NOT NULL,
    message             TEXT,
    requested_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at        TIMESTAMP,
    UNIQUE(entrepreneur_email, investor_email),
    CONSTRAINT fk_conn_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_conn_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_conn_entrepreneur ON connections(entrepreneur_email, status);
CREATE INDEX idx_conn_investor ON connections(investor_email, status);
CREATE INDEX idx_conn_status ON connections(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- 12. INVESTOR_INTERESTS - Investor interest tracking
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investor_interests (
    interest_id         SERIAL PRIMARY KEY,
    investor_email      VARCHAR(255) NOT NULL,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    status              VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'withdrawn')),
    message             TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(investor_email, entrepreneur_email),
    CONSTRAINT fk_ii_investor FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_ii_entrepreneur FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_ii_investor ON investor_interests(investor_email, status, created_at DESC);
CREATE INDEX idx_ii_entrepreneur ON investor_interests(entrepreneur_email, status, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- INVESTMENTS - Investment records
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investments (
    investment_id       SERIAL PRIMARY KEY,
    investor_email      VARCHAR(255) NOT NULL,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    startup_name        VARCHAR(255),
    investment_amount   DECIMAL(15,2),
    equity_percentage   DECIMAL(5,2),
    investment_date     DATE,
    investment_stage    VARCHAR(100),
    status              VARCHAR(50) DEFAULT 'proposed' CHECK (status IN ('proposed', 'active', 'completed')),
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(investor_email, entrepreneur_email),
    CONSTRAINT fk_inv_investor FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_inv_entrepreneur FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_inv_investor ON investments(investor_email);
CREATE INDEX idx_inv_entrepreneur ON investments(entrepreneur_email);

-- ─────────────────────────────────────────────────────────────────────────────
-- 14. MESSAGES - Direct messages
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    message_id          SERIAL PRIMARY KEY,
    sender_email        VARCHAR(255) NOT NULL,
    receiver_email      VARCHAR(255) NOT NULL,
    message_text        TEXT NOT NULL,
    is_read             BOOLEAN DEFAULT FALSE,
    sent_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at             TIMESTAMP,
    CONSTRAINT fk_msg_sender FOREIGN KEY (sender_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_msg_receiver FOREIGN KEY (receiver_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_msg_receiver ON messages(receiver_email, sent_at DESC);
CREATE INDEX idx_msg_sender ON messages(sender_email, sent_at DESC);
CREATE INDEX idx_msg_unread ON messages(receiver_email, is_read);

-- ─────────────────────────────────────────────────────────────────────────────
-- 15. NOTIFICATIONS - In-platform notifications
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    notification_id     SERIAL PRIMARY KEY,
    email               VARCHAR(255) NOT NULL,
    type                VARCHAR(100) NOT NULL CHECK (type IN (
        'connection_request', 'connection_accepted', 'post_liked', 'post_commented',
        'post_saved', 'investor_interested', 'new_message', 'profile_viewed', 'system'
    )),
    title               VARCHAR(255),
    body                TEXT,
    related_post_id     INTEGER,
    related_user_email  VARCHAR(255),
    is_read             BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_notif_email ON notifications(email, created_at DESC);
CREATE INDEX idx_notif_unread ON notifications(email, is_read);

-- ─────────────────────────────────────────────────────────────────────────────
-- 16. PROFILE_VIEW_LOGS - Profile view tracking
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS profile_view_logs (
    log_id              SERIAL PRIMARY KEY,
    viewed_email        VARCHAR(255) NOT NULL,
    viewer_email        VARCHAR(255),
    viewed_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pvl_viewed FOREIGN KEY (viewed_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_pvl_viewed ON profile_view_logs(viewed_email, viewed_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 17. AI_CHAT_SESSIONS - Entrepreneur AI chat sessions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_chat_sessions (
    session_id          VARCHAR(64) PRIMARY KEY,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    mode                VARCHAR(50) NOT NULL DEFAULT 'guidance' CHECK (mode IN ('guidance', 'intermediary')),
    investor_email      VARCHAR(255),
    title               VARCHAR(200) DEFAULT 'New Chat',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_acs_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_acs_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE SET NULL
);
CREATE INDEX idx_acs_ent_email ON ai_chat_sessions(entrepreneur_email);
CREATE INDEX idx_acs_updated ON ai_chat_sessions(updated_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 18. AI_CHAT_MESSAGES - Entrepreneur AI chat messages
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_chat_messages (
    id                  BIGSERIAL PRIMARY KEY,
    session_id          VARCHAR(64) NOT NULL,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    mode                VARCHAR(50) NOT NULL CHECK (mode IN ('guidance', 'intermediary')),
    role                VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content             TEXT NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_acm_session FOREIGN KEY (session_id) REFERENCES ai_chat_sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT fk_acm_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_acm_session ON ai_chat_messages(session_id);
CREATE INDEX idx_acm_ent_email ON ai_chat_messages(entrepreneur_email);
CREATE INDEX idx_acm_created ON ai_chat_messages(created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 19. INV_CHAT_SESSIONS - Investor AI chat sessions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inv_chat_sessions (
    session_id          VARCHAR(64) PRIMARY KEY,
    investor_email      VARCHAR(255) NOT NULL,
    mode                VARCHAR(50) NOT NULL DEFAULT 'guidance' CHECK (mode IN ('guidance', 'intermediate')),
    entrepreneur_email  VARCHAR(255),
    title               VARCHAR(200) DEFAULT 'New Chat',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ics_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_ics_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE SET NULL
);
CREATE INDEX idx_ics_inv_email ON inv_chat_sessions(investor_email);
CREATE INDEX idx_ics_updated ON inv_chat_sessions(updated_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 20. INV_CHAT_MESSAGES - Investor AI chat messages
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inv_chat_messages (
    id                  BIGSERIAL PRIMARY KEY,
    session_id          VARCHAR(64) NOT NULL,
    investor_email      VARCHAR(255) NOT NULL,
    mode                VARCHAR(50) NOT NULL CHECK (mode IN ('guidance', 'intermediate')),
    role                VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content             TEXT NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_icm_session FOREIGN KEY (session_id) REFERENCES inv_chat_sessions(session_id) ON DELETE CASCADE,
    CONSTRAINT fk_icm_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_icm_session ON inv_chat_messages(session_id);
CREATE INDEX idx_icm_inv_email ON inv_chat_messages(investor_email);
CREATE INDEX idx_icm_created ON inv_chat_messages(created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 21. MEETINGS - Meeting schedules
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meetings (
    meeting_id          SERIAL PRIMARY KEY,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    investor_email      VARCHAR(255) NOT NULL,
    meeting_type        VARCHAR(100),
    scheduled_at        TIMESTAMP,
    status              VARCHAR(50) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_meet_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_meet_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_meet_entrepreneur ON meetings(entrepreneur_email, scheduled_at);
CREATE INDEX idx_meet_investor ON meetings(investor_email, scheduled_at);
CREATE INDEX idx_meet_status ON meetings(status);

-- ─────────────────────────────────────────────────────────────────────────────
-- 22. DEALS - Deal pipeline
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deals (
    deal_id             SERIAL PRIMARY KEY,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    investor_email      VARCHAR(255) NOT NULL,
    deal_stage          VARCHAR(50) DEFAULT 'introduced' CHECK (deal_stage IN ('introduced', 'in_discussion', 'due_diligence', 'term_sheet', 'closed')),
    deal_value          DECIMAL(15,2),
    equity_offered      DECIMAL(5,2),
    status              VARCHAR(50) DEFAULT 'active',
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entrepreneur_email, investor_email),
    CONSTRAINT fk_deal_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_deal_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_deal_entrepreneur ON deals(entrepreneur_email, deal_stage);
CREATE INDEX idx_deal_investor ON deals(investor_email, deal_stage);
CREATE INDEX idx_deal_stage ON deals(deal_stage);

-- ─────────────────────────────────────────────────────────────────────────────
-- USER_EMBEDDINGS - Pre-computed AI embeddings for matching
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_embeddings (
    email               VARCHAR(255) PRIMARY KEY,
    role                VARCHAR(50) NOT NULL CHECK (role IN ('entrepreneur', 'investor')),
    embedding           TEXT NOT NULL,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ue_email FOREIGN KEY (email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_ue_role ON user_embeddings(role);

-- ─────────────────────────────────────────────────────────────────────────────
-- AI_MATCH_CACHE - Cached match scores
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_match_cache (
    cache_id            SERIAL PRIMARY KEY,
    investor_email      VARCHAR(255) NOT NULL,
    entrepreneur_email  VARCHAR(255) NOT NULL,
    score               DECIMAL(6,4) NOT NULL,
    direction           VARCHAR(50) NOT NULL CHECK (direction IN ('investor_to_entrepreneur', 'entrepreneur_to_investor')),
    computed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(investor_email, entrepreneur_email, direction),
    CONSTRAINT fk_amc_inv FOREIGN KEY (investor_email) REFERENCES login_data(email) ON DELETE CASCADE,
    CONSTRAINT fk_amc_ent FOREIGN KEY (entrepreneur_email) REFERENCES login_data(email) ON DELETE CASCADE
);
CREATE INDEX idx_amc_inv_dir ON ai_match_cache(investor_email, direction, score DESC);
CREATE INDEX idx_amc_ent_dir ON ai_match_cache(entrepreneur_email, direction, score DESC);

-- ═════════════════════════════════════════════════════════════════════════════
-- END OF SCHEMA
-- ═════════════════════════════════════════════════════════════════════════════
