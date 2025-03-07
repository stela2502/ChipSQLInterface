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
                    'start': int(parts[3]),
                    'stop': int(parts[4]),
                    'strand': parts[6]
                }

                # Adjust gene orientation if necessary (based on strand)
                if gene_info['strand'] == '-':
                    gene_info['start'], gene_info['stop'] = gene_info['stop'], gene_info['start']

                gene_data.append(gene_info)

            elif parts[2] == 'transcript':
                # Extract transcript data
                transcript_info = {
                    'transcript_name': parts[8].split('transcript_id "')[1].split('"')[0],
                    'chromosome': parts[0],
                    'start': int(parts[3]),
                    'stop': int(parts[4]),
                    'strand': parts[6]
                }

                # Adjust transcript position based on strand (gene orientation)
                if transcript_info['strand'] == '-':
                    transcript_info['start'], transcript_info['stop'] = transcript_info['stop'], transcript_info['start']

                transcript_data.append(transcript_info)

    # Insert genes into the database
    for gene in gene_data:
        cur.execute("""
            INSERT INTO genes (gene_name, chromosome, start, stop) 
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (gene['gene_name'], gene['chromosome'], gene['start'], gene['stop']))
        gene_id = cur.fetchone()[0]

        # Insert transcripts linked to the gene_id
        for transcript in transcript_data:
            # Insert transcript into the database
            cur.execute("""
                INSERT INTO transcripts (gene_id, transcript_name,  start, stop) 
                VALUES (%s, %s, %s, %s)
            """, (gene_id, transcript['transcript_name'], transcript['start'], transcript['stop']))

    conn.commit()

    # Create indexes on chromosome, start, and stop for efficient querying
    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_genes_chromosome_start_end ON genes(chromosome, start, stop);
    CREATE INDEX IF NOT EXISTS idx_genes_chromosome_start ON genes(chromosome, start );
    CREATE INDEX IF NOT EXISTS idx_gene ON transcripts( gene_id );
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
