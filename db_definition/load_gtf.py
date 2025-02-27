#!/usr/bin/env python3

import os
import psycopg2
import argparse

def create_connection(password):
    conn = psycopg2.connect(dbname='genome_db', user='postgres', password=password, host='localhost')
    return conn

def load_gtf_to_postgres(gtf_file, password):
    conn = create_connection(password)
    cur = conn.cursor()

    cur.execute( f" INSERT INTO info ( info ) VALUES ( 'gene info from {gtf_file}' )" )
    # Process GTF file into genes and transcripts
    gene_data = []
    transcript_data = []

    with open(gtf_file, 'r') as gtf:
        for line in gtf:
            if line.startswith('#'):
                continue
            parts = line.strip().split('\t')
            if parts[2] == 'gene':
                # Extract gene data
                gene_info = {
                    'gene_name': parts[8].split('gene_name "')[1].split('"')[0],
                    'chromosome': parts[0],
                    'start_pos': int(parts[3]),
                    'end_pos': int(parts[4]),
                    'strand': parts[6]
                }

                # Adjust gene orientation if necessary (based on strand)
                if gene_info['strand'] == '-':
                    gene_info['start_pos'], gene_info['end_pos'] = gene_info['end_pos'], gene_info['start_pos']

                gene_data.append(gene_info)

            elif parts[2] == 'transcript':
                # Extract transcript data
                transcript_info = {
                    'transcript_name': parts[8].split('transcript_id "')[1].split('"')[0],
                    'chromosome': parts[0],
                    'start_pos': int(parts[3]),
                    'end_pos': int(parts[4]),
                    'strand': parts[6]
                }

                # Adjust transcript position based on strand (gene orientation)
                if transcript_info['strand'] == '-':
                    transcript_info['start_pos'], transcript_info['end_pos'] = transcript_info['end_pos'], transcript_info['start_pos']

                transcript_data.append(transcript_info)

    # Insert genes into the database
    for gene in gene_data:
        cur.execute("""
            INSERT INTO genes (gene_name, chromosome, start_pos, end_pos, strand) 
            VALUES (%s, %s, %s, %s, %s) RETURNING gene_id
        """, (gene['gene_name'], gene['chromosome'], gene['start_pos'], gene['end_pos'], gene['strand']))
        gene_id = cur.fetchone()[0]

        # Insert transcripts linked to the gene_id
        for transcript in transcript_data:
            # Insert transcript into the database
            cur.execute("""
                INSERT INTO transcripts (gene_id, transcript_name, chromosome, start_pos, end_pos, strand) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (gene_id, transcript['transcript_name'], transcript['chromosome'], transcript['start_pos'], transcript['end_pos'], transcript['strand']))

    conn.commit()

    # Create indexes on chromosome, start_pos, and end_pos for efficient querying
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_genes_chromosome_start_end ON genes(chromosome, start_pos, end_pos);
    CREATE INDEX IF NOT EXISTS idx_transcripts_chromosome_start_end ON transcripts(chromosome, start_pos, end_pos);
    """)

    cur.close()
    conn.close()

def main():
    # Setup command-line argument parser
    parser = argparse.ArgumentParser(description="Load GTF data into PostgreSQL database")
    parser.add_argument('gtf_file', help="Path to the GTF file to load")
    parser.add_argument('--password', help="Password for the database - is uniqe to each apptainer image")

    # Parse the arguments
    args = parser.parse_args()

    # Call the function to load the GTF file into the database
    load_gtf_to_postgres(args.gtf_file, args.password)

if __name__ == '__main__':
    main()
