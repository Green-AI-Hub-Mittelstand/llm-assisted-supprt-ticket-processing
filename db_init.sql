CREATE EXTENSION IF NOT EXISTS vector;

-- create rerank function
CREATE OR REPLACE FUNCTION rrf_score(rank bigint, rrf_k int DEFAULT 50)
RETURNS numeric
LANGUAGE SQL
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT COALESCE(1.0 / ($1 + $2), 0.0);
$$;

-- create manual table
CREATE TABLE IF NOT EXISTS manuals
(
    id bigserial PRIMARY KEY;
    chunk text,
    chunk_embedding vector(512),
    page_number integer,
    devicetype text,
    devicemodel_used boolean,
    url text,
    doctype text,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS manuals_chunk_embedding_idx
    ON manuals USING hnsw
    (chunk_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS manuals_to_tsvector_idx
    ON manuals USING gin
    (to_tsvector('english'::regconfig, chunk));

-- create ticket table

CREATE TABLE IF NOT EXISTS tickets
(
    id bigserial PRIMARY KEY,
    chunk text,
    chunk_embedding vector(512),
    devicetype text,
    ticketid text,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS tickets_chunk_embedding_idx
ON public.tickets USING hnsw
(chunk_embedding vector_cosine_ops);

-- Index: tickets_to_tsvector_idx

-- DROP INDEX IF EXISTS public.tickets_to_tsvector_idx;

CREATE INDEX IF NOT EXISTS tickets_to_tsvector_idx
    ON public.tickets USING gin
    (to_tsvector('english'::regconfig, chunk));