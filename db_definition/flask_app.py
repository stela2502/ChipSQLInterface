import os
import io
from flask import Flask, url_for, request, redirect, Response, jsonify, render_template
#import psycopg2
import sqlite3
from werkzeug.utils import secure_filename
import csv
import getpass
import subprocess

app = Flask(__name__)

# Set the allowed file extensions for BED files
ALLOWED_EXTENSIONS = {'bed'}


import socket
#https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib#comment7578202_166506
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


# Function to check the file extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to create a database connection
def create_connection():

    pgdata_path = os.getenv("PGDATA")
    # Check if PGDATA exists
    if not pgdata_path:
        raise ValueError("PGDATA environment variable is not set!")

    # Check if the PGDATA directory exists
    if not os.path.exists(pgdata_path):
        raise ValueError(f"database path is not existsig '{pgdata_path}'!")

    # Define the database file path
    db_path = os.path.join(pgdata_path, "genome.db")
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        sql_file_path = "/etc/setup_db.sql"
        with open(sql_file_path, 'r') as file:
            sql_script = file.read()
            cursor.executescript(sql_script)
        print("Database initialized")
        return conn
    else:
        conn = sqlite3.connect(db_path)
        return conn


# Route for the default landing page
@app.route('/')
def index():
    conn = create_connection()
    if conn:
        cur = conn.cursor()

        # Fetch genome version (assuming a metadata table with genome_version)
        cur.execute("SELECT info FROM info LIMIT 1;")
        genome_version_row = cur.fetchone()
        genome_version = genome_version_row[0] if genome_version_row else "Nothing"

        cur.execute("SELECT count(*) FROM genes;")

        gene_counts = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM transcripts;")

        transcript_counts = cur.fetchone()[0]


        error_message = ""
        if genome_version == "Nothing":
            error_message ="Please upload your gtf information make sure the genome version of the gtf matches to your bed files!";



        # Fetch the number of experiments
        cur.execute("SELECT COUNT(*) FROM experiments;")
        num_experiments = cur.fetchone()[0]

        # Fetch the number of peaks per experiment
        cur.execute("""SELECT experiment_id, COUNT(experiment_id)
            from bed Group By experiment_id """
        )
        peaks_per_experiment = cur.fetchall()

        # Fetch existing experiments
        cur.execute("SELECT id, experiment_name FROM experiments;")
        experiments = cur.fetchall()  # List of tuples (id, experiment_name)
        experiment_dict = {exp_id: exp_name for exp_id, exp_name in experiments}

        print( f"The experiment dict: {experiment_dict}")
        cur.close()
        conn.close()

        # Prepare the data to be displayed
        peaks_info = {}
        for exp_id, peak_count in peaks_per_experiment:
            exp_name = experiment_dict.get(exp_id, "Unknown Experiment")
            peaks_info[exp_name] =  peak_count 

        error_message += request.args.get('error_message', "")  # Get error message from URL
        
        # Render the landing page with the fetched data
        return render_template(
            'index.html',
            genome_version=genome_version,
            num_experiments=num_experiments,
            gene_counts=gene_counts,
            transcript_counts=transcript_counts,
            peaks_info=peaks_info,
            experiments=[{"id": exp[0], "experiment_name": exp[1]} for exp in experiments],  # Convert tuples to dicts
            error_message=error_message  # Pass error message to template
        )
    else:
        return "Database connection error!", 500

# Route to handle the BED file upload
@app.route('/upload_bed', methods=['POST'])
def upload_bed():

    # Check if the user selected an existing experiment or entered a new one
    experiment_id = request.form.get("experiment_id")
    new_experiment_name = request.form.get("new_experiment_name")
    new_experiment_description = request.form.get("new_experiment_description")

    

    if new_experiment_name:  # If the user provided a new experiment name, insert it into the DB
        conn = create_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO experiments (experiment_name, description) VALUES (?, ?);",
            (new_experiment_name, new_experiment_description)
        )
        experiment_id = cur.lastrowid  # Get the new experiment ID
        conn.commit()
        cur.close()

    if not experiment_id:  # Safety check
        error_message = "No experiment id selected and not enough data to create a new one"
        return redirect(url_for('index', error_message=error_message))  # Redirect on error

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)

        # Process the BED file and insert it into the database
        result = process_bed_file_in_memory(file, experiment_id)
        if result:
            return redirect(url_for('index'))
            #return jsonify({"success": "BED file uploaded and data inserted into the database"}), 200
        else:
            error_message = "error: Failed to process the BED file"
            return redirect(url_for('index', error_message=error_message))
    else:
        error_message = "An error occurred"
        return redirect(url_for('index', error_message=error_message))

# Function to process the BED file from memory and insert into the database
def process_bed_file_in_memory(file, experiment_id):
    conn = create_connection()
    if conn:
        cur = conn.cursor()

        # Open the file (assuming `file` is a path or file-like object)
        if isinstance(file, str):  # If file is a path
            with open(file, 'r') as f:
                lines = f.readlines()
        else:  # If file is a file-like object (e.g., from Flask request)
            lines = file.stream

        id_ = 0

        bed_data = []

        for raw_line in lines:
            id_ +=1
            line = raw_line.decode("utf-8")  # Decode bytes to str
            if line.startswith('#'):  # Skip comment lines
                continue
            parts = line.strip().split('\t')
            
            if len(parts) >= 3:
                # Extract the necessary columns from the BED file
                chromosome = parts[0]
                start = int(parts[1])
                stop = int(parts[2])
                peak_score = float(parts[4]) if len(parts) > 4 else 0.0
                feature_name = parts[3] if len(parts) > 3 else "-"
                bed_data.append( [ experiment_id, chromosome, start, stop, peak_score, feature_name ] );            
            else:
               error_message = f"error on bed file line {id_}" 
               return redirect(url_for('index', error_message=error_message))
        try:
            cur.executemany( 
                "INSERT INTO bed (experiment_id, chromosome, start, stop, peak_score, feature_name) VALUES (?, ?, ?, ?, ?, ?)", 
                bed_data
                )
            conn.commit()
            conn.close()
        except Exception as e:
            return redirect(url_for('index', error_message= f"Line {id_}: Unexpected error: {e}"))
        return True
    return False

#-- Table for storing BED data (linking to experiments)
#CREATE TABLE bed (
#    id SERIAL PRIMARY KEY,              -- Unique ID for each BED entry
#    experiment_id INT NOT NULL,         -- Foreign key linking to experiments
#    chromosome TEXT NOT NULL,           -- Chromosome where the peak is located
#    start INT NOT NULL,                 -- Start position of the peak
#    stop INT NOT NULL,                   -- End position of the peak
#    peak_score FLOAT,                   -- Optional: Peak score or other metric
#    feature_name TEXT,                  -- Optional: Name of the feature (e.g., TF or region)
#    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
#);
# Function to process the BED file and insert into the database
def process_bed_file(file_path, experiment_id):
    conn = create_connection()
    if conn:
        cur = conn.cursor()

        with open(file_path, 'r') as bed_file:
            for line in bed_file:
                if line.startswith('#'):  # Skip comment lines
                    continue
                parts = line.strip().split('\t')
                if len(parts) >= 3:
                    # Extract the necessary columns from the BED file
                    chromosome = parts[0]
                    start = int(parts[1])
                    end = int(parts[2])
                    peak_score = float(parts[4]) if len(parts) > 4 else None
                    feature_name = parts[3] if len(parts) > 3 else None

                    # Insert the data into the database
                    cur.execute("""
                        INSERT INTO bed (experiment_id, chromosome, start, end, peak_score, feature_name)
                        VALUES (?, ?, ?, ?, ?)
                    """, (experiment_id, chromosome, start, end, peak_score, feature_name))

        conn.commit()
        cur.close()
        conn.close()
        return True
    return False

# Function to check if the file is a valid BED file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'bed'}


def get_genes_near_peaks(distance):
    # Connect to the SQLite database
    conn = create_connection()  # Make sure to provide the path to your database
    if conn:
        cur = conn.cursor()
        try:
            # Define the SQL query
            query = """
                SELECT
                    g.id AS gene_id,
                    g.gene_name,
                    g.chromosome,
                    g.start AS gene_start,
                    g.stop AS gene_stop,
                    b.id AS bed_id,
                    e.experiment_name,
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
                JOIN experiments e ON b.experiment_id = e.id
                WHERE (g.start - ? <= b.stop AND g.stop + ? >= b.start)
                ORDER BY g.chromosome, g.start;
            """
            # Execute the query with the provided distance as a parameter
            cur.execute(query, (distance, distance))

            # Fetch all results
            results = cur.fetchall()

            # Close the cursor and connection
            cur.close()
            conn.close()

            return results
        except Exception as e:
            print(f"Error executing query: {e}")
            return None
    else:
        return None


# Route to handle the download of the CSV file
@app.route("/get_genes", methods=["POST"])
def get_genes():
    try:
        # Get the distance parameter from the query string
        distance = request.form.get("distance", type=int)

        if not distance:
            return f"Please provide a valid distance parameter - not '{distance}'"

        # Call the function to get genes near peaks
        results = get_genes_near_peaks(distance)

        if results:
            # Prepare the CSV output
            output = io.StringIO()
            writer = csv.writer(output, delimiter="\t" )
            #    gene_id INT,    gene_name TEXT,    chromosome TEXT,    gene_start INT,    gene_stop INT,    bed_id INT,    experiment_id INT,    bed_chromosome TEXT,    bed_start INT,    bed_stop INT,    peak_score FLOAT,    feature_name TEXT,    distance INT            writer.writerow(["Gene ID", "Gene Name", "Peak ID", "Distance (bp)"])  
            # Header row based on the table structure
            writer.writerow([
                "Gene ID", "Gene Name", "Chromosome", "Gene Start", "Gene Stop", "BED ID", 
                "Experiment ID", "BED Chromosome", "BED Start", "BED Stop", "Peak Score", 
                "Feature Name", "Distance (bp)"
            ])  # header row
            # Write the data rows
            writer.writerows(results)

            output.seek(0)

            # Create a response to trigger a download
            return Response(
                output,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment;filename=genes_near_peaks.csv"},
            )
        else:
            return "No results found for the given distance."

    except Exception as e:
        return f"An error occurred: {e}"


# Route to handle the download of the CSV file
@app.route("/upload_gtf", methods=["POST"])
def upload_gtf():
    try:
        # Get the distance parameter from the query string
        gtf_file = request.files.get("gtffile")

        if not gtf_file:
            return f"Please provide a valid file - not '{gtf_file}'"

        #raise RuntimeError( f"What have I gotten here: '{gtf_file.filename}'??")
        # Call the function to get genes near peaks
        load_gtf_to_postgres(gtf_file)

        return redirect(url_for('index'))
    except Exception as e:
        return f"An error occurred: {e}"


def load_gtf_to_postgres(gtf_file):
    """Loads a GTF file into a PostgreSQL database using a temporary SQL dump for efficiency."""

    conn = create_connection()
    cur = conn.cursor()

    # Check if GTF has already been uploaded
    cur.execute("SELECT info FROM info LIMIT 1;")
    genome_version = cur.fetchone()[0] if cur.rowcount > 0 else "Nothing"

    if genome_version != "Nothing":
        return "Error: GTF has already been uploaded"

    cur.execute(f"INSERT INTO info (info) VALUES ('gene info from {gtf_file.filename}');")
    conn.commit()

    pgdata_path = os.getenv("PGDATA")
    if pgdata_path:
        print(f"PGDATA is set to: {pgdata_path}")
    else:
        print("PGDATA is not set.")

    temp_sql_path = os.path.join(pgdata_path, "temp_import.sql")
    gene_id_counter = 1  # Start counting genes from 1


    # Buffers for bulk insertion
    gene_entries = []
    transcript_entries = []

    for raw_line in gtf_file.stream:
        line = raw_line.decode("utf-8").strip()
        if line.startswith("#"):
            continue
        
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        
        feature_type = parts[2]
        chromosome = parts[0]
        start = int(parts[3])
        stop = int(parts[4])
        strand = parts[6]
        attributes = parts[8]

        if feature_type == "gene":
            gene_name = extract_attribute(attributes, "gene_name")
            if gene_name:
                if strand == "-":
                    start, stop = stop, start  # Adjust for reverse strand
                gene_entries.append( (gene_name,chromosome,start,stop ))
                gene_id_counter += 1  # Increment for the next gene

        elif feature_type == "transcript":
            transcript_name = extract_attribute(attributes, "transcript_id")
            if transcript_name:
                if strand == "-":
                    start, stop = stop, start  # Adjust for reverse strand
                transcript_entries.append((gene_id_counter-1 ,transcript_name , start, stop ) )
    # just for debug!           
    f_name = os.path.join(pgdata_path, "db_gtf_contents_file.sql" )


    # Write COPY commands to the SQL file
    if gene_entries:
        cur.executemany(
            "INSERT INTO genes (gene_name, chromosome, start, stop) VALUES (?, ?, ?, ?)", 
            gene_entries)

    if transcript_entries:
        cur.executemany(
            "INSERT INTO transcripts (gene_id, transcript_name, start, stop)  VALUES (?, ?, ?, ?)", 
            transcript_entries)

    cur.execute ( "CREATE INDEX IF NOT EXISTS idx_genes_chromosome_start ON genes(chromosome, start)")
    cur.execute ( "CREATE INDEX IF NOT EXISTS idx_transcripts_gene_id ON transcripts(gene_id)")

    conn.commit()
    conn.close()
        
    return "Data successfully loaded and indexes created"


def extract_attribute(attributes, key):
    """Extracts values from a GTF attributes column (e.g., gene_name or transcript_id)."""
    for attr in attributes.split(";"):
        attr = attr.strip()
        if attr.startswith(key):
            parts = attr.split('"')
            if len(parts) > 1:
                return parts[1]
    return None

# Main entry point for Flask app
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
