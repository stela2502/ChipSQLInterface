-- Table for storing experiments (e.g., ChIP-seq experiments)

CREATE TABLE experiments (
    id SERIAL PRIMARY KEY,              -- Experiment ID
    experiment_name TEXT NOT NULL,       -- Name of the experiment (e.g., "ChIP-seq experiment 1")
    description TEXT                    -- Description of the experiment
);

CREATE Table info (
    id SERIAL PRIMARY KEY,              -- info ID
    info TEXT
);


-- Table for storing genes
CREATE TABLE genes (
    id SERIAL PRIMARY KEY,              -- Gene ID
    gene_name TEXT NOT NULL,            -- Gene name (e.g., "BRCA1")
    chromosome TEXT NOT NULL,           -- Chromosome where the gene is located
    start INT,                          -- Start position of the gene
    stop INT                             -- End position of the gene
);

-- Table for storing transcripts (linked to genes, with alternative start and stop positions)
CREATE TABLE transcripts (
    id SERIAL PRIMARY KEY,              -- Transcript ID (for different isoforms)
    gene_id INT NOT NULL,               -- Foreign key linking to genes table
    transcript_name TEXT NOT NULL,      -- Name of the transcript (e.g., "BRCA1_Transcript_1")
    start INT,                          -- Start position of this transcript
    stop INT,                            -- End position of this transcript
    FOREIGN KEY (gene_id) REFERENCES genes(id)  -- Link to the gene this transcript belongs to
);

-- Table for storing BED data (linking to experiments)
CREATE TABLE bed (
    id SERIAL PRIMARY KEY,              -- Unique ID for each BED entry
    experiment_id INT NOT NULL,         -- Foreign key linking to experiments
    chromosome TEXT NOT NULL,           -- Chromosome where the peak is located
    start INT NOT NULL,                 -- Start position of the peak
    stop INT NOT NULL,                   -- End position of the peak
    peak_score FLOAT,                   -- Optional: Peak score or other metric
    feature_name TEXT,                  -- Optional: Name of the feature (e.g., TF or region)
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

CREATE OR REPLACE FUNCTION get_genes_near_peaks( dist INT)
RETURNS TABLE (
    gene_id INT,
    gene_name TEXT,
    chromosome TEXT,
    gene_start INT,
    gene_stop INT,
    bed_id INT,
    experiment_id INT,
    bed_chromosome TEXT,
    bed_start INT,
    bed_stop INT,
    peak_score FLOAT,
    feature_name TEXT,
    distance INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        g.id AS gene_id,
        g.gene_name,
        g.chromosome,
        g.start AS gene_start,
        g.stop AS gene_stop,
        b.id AS bed_id,
        b.experiment_id,
        b.chromosome AS bed_chromosome,
        b.start AS bed_start,
        b.stop AS bed_stop,
        b.peak_score,
        b.feature_name,
        CASE
            -- Gene is to the right of the peak
            WHEN g.start > b.stop THEN g.start - b.stop
            -- Gene is to the left of the peak
            WHEN g.stop < b.start THEN b.start - g.stop
            -- Gene overlaps the peak
            ELSE 0
        END AS distance
    FROM genes g
    JOIN bed b ON g.chromosome = b.chromosome
    WHERE (g.start - dist <= b.stop AND g.stop + dist >= b.start);
    END;
$$ LANGUAGE plpgsql;
