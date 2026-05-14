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
  metadata jsonb default '{}'::jsonb
);

create index if not exists memories_embedding_idx
  on memories using hnsw (embedding vector_cosine_ops);

create table if not exists sessions (
  id uuid primary key,
  started_at timestamptz default now(),
  ended_at timestamptz,
  metadata jsonb default '{}'::jsonb
);

create table if not exists messages (
  id uuid primary key,
  session_id uuid references sessions(id),
  role varchar(50) not null,
  content text not null,
  timestamp timestamptz default now()
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
