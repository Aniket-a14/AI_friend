-- Enable the pgvector extension to work with embedding vectors
create extension if not exists vector;
create extension if not exists pgcrypto;

-- Create a table to store long-term memories
create table if not exists memories (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  embedding vector(768), -- Gemini 1.5 Flash/Pro embedding dimension
  importance_score double precision not null default 0.5,
  emotional_weight double precision not null default 0.0,
  certainty double precision not null default 1.0,
  source text not null default 'user',
  last_recalled_at timestamptz default now(),
  created_at timestamptz default now(),
  metadata jsonb default '{}'::jsonb
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
