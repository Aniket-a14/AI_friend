-- Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;
create extension if not exists pgcrypto;

-- Create a table to store long-term memories
create table if not exists memories (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  raw_content text, -- Verbatim Truth
  wing text not null default 'personal',
  room text,
  embedding vector(768), -- Gemini 1.5 Flash/Pro embedding dimension
  importance_score double precision not null default 0.5,
  emotional_weight double precision not null default 0.0,
  valence double precision not null default 0.0,
  certainty double precision not null default 1.0,
  source text not null default 'user',
  recall_count integer not null default 0,
  last_recalled_at timestamptz default now(),
  created_at timestamptz default now(),
  metadata jsonb default '{}'::jsonb,
  lifespan_stage varchar(100),
  crisis varchar(100),
  virtue varchar(100),
  relations varchar(255),
  relation_circles varchar(255),
  modality varchar(255)
);

-- Create a table to store cold archived decayed memories
create table if not exists archived_memories (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  raw_content text,
  wing text not null default 'personal',
  room text,
  importance_score double precision not null default 0.5,
  emotional_weight double precision not null default 0.0,
  valence double precision not null default 0.0,
  certainty double precision not null default 1.0,
  source text not null default 'user',
  recall_count integer not null default 0,
  last_recalled_at timestamptz default now(),
  created_at timestamptz default now(),
  metadata jsonb default '{}'::jsonb,
  lifespan_stage varchar(100),
  crisis varchar(100),
  virtue varchar(100),
  relations varchar(255),
  relation_circles varchar(255),
  modality varchar(255),
  embedding halfvec(768)
);

-- Schema migrations for existing tables
alter table memories add column if not exists lifespan_stage varchar(100);
alter table memories add column if not exists crisis varchar(100);
alter table memories add column if not exists virtue varchar(100);
alter table memories add column if not exists relations varchar(255);
alter table memories add column if not exists relation_circles varchar(255);
alter table memories add column if not exists modality varchar(255);

create index if not exists memories_embedding_idx
  on memories using hnsw (embedding vector_cosine_ops);

create index if not exists archived_memories_embedding_idx
  on archived_memories using hnsw (embedding halfvec_cosine_ops);

create table if not exists sessions (
  id uuid primary key,
  started_at timestamptz default now(),
  ended_at timestamptz,
  trust_benevolence double precision default 0.5,
  trust_competence double precision default 0.5,
  trust_integrity double precision default 0.5,
  metadata jsonb default '{}'::jsonb
);

create table if not exists messages (
  id uuid primary key,
  session_id uuid references sessions(id),
  role varchar(50) not null,
  content text not null,
  timestamp timestamptz default now(),
  consolidated boolean default false
);

create table if not exists agent_configs (
  id integer primary key,
  personality jsonb,
  background_history jsonb,
  evolved_learnings text,
  updated_at timestamptz default now()
);

-- Create a function to search for memories
-- usage: select * from match_memories(embedding, match_threshold, match_count)
create or replace function match_memories (
  query_embedding vector(768),
  match_threshold float,
  match_count int
)
returns table (
  id uuid,
  content text,
  similarity float
)
language sql stable
as $$
  select
    id,
    content,
    1 - (memories.embedding <=> query_embedding) as similarity
  from memories
  where 1 - (memories.embedding <=> query_embedding) > match_threshold
  order by memories.embedding <=> query_embedding
  limit match_count;
$$;

-- Create a high-performance ACT-R Based memory surfacing function
-- usage: select * from surface_actr_memories(query_embedding, wing, room, decay_rate, spread_weight, emotion_weight, current_valence, threshold, limit, simulated_time)
create or replace function surface_actr_memories (
  query_embedding vector(768),
  p_wing text,
  p_room text,
  p_decay_rate double precision,
  p_spread_weight double precision,
  p_emotion_weight double precision,
  p_current_valence double precision,
  p_current_arousal double precision,
  p_current_cortisol double precision,
  p_threshold double precision,
  p_limit int,
  p_simulated_time timestamptz default null
)
returns table (
  content text,
  raw_content text,
  wing text,
  room text,
  importance_score double precision,
  emotional_weight double precision,
  valence double precision,
  recall_count integer,
  last_recalled_at timestamptz,
  created_at timestamptz,
  metadata jsonb,
  similarity double precision,
  score double precision
)
language plpgsql stable
as $$
declare
  now_ts timestamptz := coalesce(p_simulated_time, clock_timestamp());
begin
  return query
  select
    m.content,
    m.raw_content,
    m.wing,
    m.room,
    m.importance_score,
    m.emotional_weight,
    m.valence,
    m.recall_count,
    m.last_recalled_at,
    m.created_at,
    m.metadata,
    (1 - (m.embedding <=> query_embedding))::double precision as similarity,
    (
      -- ACT-R Base-Level Activation (B_i)
      -- ln(greatest(1, recall_count)) - decay * ln(hours_since + 1) + 1.5 * importance_score + 0.15 * (1 - dist_emo)
      ln(greatest(1, m.recall_count))
      - p_decay_rate * ln(greatest(0.001, extract(epoch from (now_ts - coalesce(m.last_recalled_at, now_ts))) / 3600.0) + 1)
      + 1.5 * coalesce(m.importance_score, 0.5)
      + 0.15 * (1.0 - sqrt(power(coalesce(m.valence, 0.0) - p_current_valence, 2) + power(coalesce(m.emotional_weight, 0.0) - p_current_arousal, 2)))

      -- Spreading Activation (Similarity with neuromodulatory gating)
      -- spread_weight * similarity * (1.0 + 0.1 * valence * emotional_weight - 0.2 * current_arousal * current_cortisol)
      + p_spread_weight * (1.0 - (m.embedding <=> query_embedding)) * (
        1.0
        + 0.1 * coalesce(m.valence, 0.0) * coalesce(m.emotional_weight, 0.0)
        - 0.2 * p_current_arousal * p_current_cortisol
      )

      -- Bower Emotional Proximity adjustment: -0.5 * dist_emo
      - 0.5 * sqrt(power(coalesce(m.valence, 0.0) - p_current_valence, 2) + power(coalesce(m.emotional_weight, 0.0) - p_current_arousal, 2))
    )::double precision as score
  from memories m
  where m.wing = p_wing
    and (p_room is null or m.room = p_room)
    and (
      (
        ln(greatest(1, m.recall_count))
        - p_decay_rate * ln(greatest(0.001, extract(epoch from (now_ts - coalesce(m.last_recalled_at, now_ts))) / 3600.0) + 1)
        + 1.5 * coalesce(m.importance_score, 0.5)
        + 0.15 * (1.0 - sqrt(power(coalesce(m.valence, 0.0) - p_current_valence, 2) + power(coalesce(m.emotional_weight, 0.0) - p_current_arousal, 2)))
        + p_spread_weight * (1.0 - (m.embedding <=> query_embedding)) * (
          1.0
          + 0.1 * coalesce(m.valence, 0.0) * coalesce(m.emotional_weight, 0.0)
          - 0.2 * p_current_arousal * p_current_cortisol
        )
        - 0.5 * sqrt(power(coalesce(m.valence, 0.0) - p_current_valence, 2) + power(coalesce(m.emotional_weight, 0.0) - p_current_arousal, 2))
      ) > p_threshold
      or m.importance_score >= 0.7
    )
  order by score desc
  limit p_limit;
end;
$$;
