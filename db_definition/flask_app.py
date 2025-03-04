import os
import io
from flask import Flask, url_for, request, redirect, Response, jsonify, render_template
import psycopg2
from werkzeug.utils import secure_filename
import csv

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

    postgres_password = "uset"
    try:
        with open('/etc/postgres_password.txt', 'r') as file:
            postgres_password = file.read().strip()
    except FileNotFoundError:
        raise ValueError("Password file not found!")

    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "genome_db"),  # Database name
            user=os.getenv("DB_USER", "postgres"),     # Database user
            password=os.getenv("DB_PASSWORD", postgres_password ),  # Database password
            host=os.getenv("DB_HOST", "localhost" )     # Database host
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

# Route for the default landing page
@app.route('/')
def index():
    conn = create_connection()
    if conn:
        cur = conn.cursor()

        # Fetch genome version (assuming a metadata table with genome_version)
        cur.execute("SELECT info FROM info LIMIT 1;")
        genome_version = cur.fetchone()[0] if cur.rowcount > 0 else "Nothing"
        
        error_message = ""
        if genome_version == "Nothing":
            error_message ="Please upload your gtf information before using this tool! USING THE COMMANDLINE TOOLS - NOT THIS SERVER!";



        # Fetch the number of experiments
        cur.execute("SELECT COUNT(*) FROM experiments;")
        num_experiments = cur.fetchone()[0]

        # Fetch the number of peaks per experiment
        cur.execute("SELECT e.experiment_name, COUNT(b.experiment_id) AS peak_count FROM experiments e LEFT JOIN bed b ON b.experiment_id = e.id Group By e.id")
        peaks_per_experiment = cur.fetchall()

        # Fetch existing experiments
        cur.execute("SELECT id, experiment_name FROM experiments;")
        experiments = cur.fetchall()  # List of tuples (id, experiment_name)

        cur.close()
        conn.close()

        # Prepare the data to be displayed
        peaks_info = {}
        for exp_id, peak_count in peaks_per_experiment:
            peaks_info[exp_id] = peak_count

        error_message += request.args.get('error_message', "")  # Get error message from URL
        
        # Render the landing page with the fetched data
        return render_template(
            'index.html',
            genome_version=genome_version,
            num_experiments=num_experiments,
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
            "INSERT INTO experiments (experiment_name, description) VALUES (%s, %s) RETURNING id;",
            (new_experiment_name, new_experiment_description)
        )
        experiment_id = cur.fetchone()[0]  # Get the new experiment ID
        conn.commit()
        cur.close()

    if not experiment_id:  # Safety check
        conn.close()
        error_message = "No experiment id selected and not enough data to create a new one"
        return redirect(url_for('index', error_message=error_message))  # Redirect on error

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join("/tmp", filename)
        file.save(file_path)

        # Process the BED file and insert it into the database
        result = process_bed_file_in_memory(file_path, experiment_id)
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
            lines = file.readlines()

        id_ = 0

        for line in lines:
            id_ +=1
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

                cur.execute("""
                    INSERT INTO bed (experiment_id, chromosome, start, stop, peak_score, feature_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """, (experiment_id, chromosome, start, stop, peak_score, feature_name))                
            else:
               error_message = f"error on bed file line {id_}" 
               return redirect(url_for('index', error_message=error_message))
        try:
            conn.commit()
        except Exception as e:
            return redirect(url_for('index', error_message= f"Line {id_}: Unexpected error: {e}"))
        cur.close()
        conn.close()
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
                        VALUES (%s, %s, %s, %s, %s)
                    """, (experiment_id, chromosome, start, end, peak_score, feature_name))

        conn.commit()
        cur.close()
        conn.close()
        return True
    return False

# Function to check if the file is a valid BED file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'bed'}


# Function to fetch genes near peaks from the database
def get_genes_near_peaks(distance):
    conn = create_connection()
    if conn:
        cur = conn.cursor()
        try:
            query = f"SELECT * from get_genes_near_peaks( {distance} )"
            cur.execute(query)
            results = cur.fetchall()
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
    conn = create_connection()
    cur = conn.cursor()

    cur.execute("SELECT info FROM info LIMIT 1;")
    genome_version = cur.fetchone()[0] if cur.rowcount > 0 else "Nothing"

    if genome_version != "Nothing":
        return "Error: GTF has already been uploaded"


    cur.execute( f" INSERT INTO info ( info ) VALUES ( 'gene info from {gtf_file.filename}' )" )
    # Process GTF file into genes and transcripts
    gene_data = []
    transcript_data = []

    for raw_line in gtf_file.stream:
        line = raw_line.decode("utf-8")  # Decode the line and remove extra whitespace
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



# Main entry point for Flask app
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
