import os
from flask import Flask, request, jsonify
import psycopg2
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Set the allowed file extensions for BED files
ALLOWED_EXTENSIONS = {'bed'}

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
            host=os.getenv("DB_HOST", "localhost")     # Database host
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
        genome_version = cur.fetchone()[0] if cur.rowcount > 0 else "Unknown"

        # Fetch the number of experiments
        cur.execute("SELECT COUNT(*) FROM experiments;")
        num_experiments = cur.fetchone()[0]

        # Fetch the number of peaks per experiment
        cur.execute("SELECT experiment_id, COUNT(*) FROM bed GROUP BY experiment_id;")
        peaks_per_experiment = cur.fetchall()

        cur.close()
        conn.close()

        # Prepare the data to be displayed
        peaks_info = {}
        for exp_id, peak_count in peaks_per_experiment:
            peaks_info[exp_id] = peak_count

        # Render the landing page with the fetched data
        return render_template('index.html', genome_version=genome_version,
                               num_experiments=num_experiments, peaks_info=peaks_info)
    else:
        return "Database connection error!", 500

# Route to handle the BED file upload
@app.route('/upload_bed', methods=['POST'])
def upload_bed():
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
        result = process_bed_file_in_memory(file_path)
        if result:
            return jsonify({"success": "BED file uploaded and data inserted into the database"}), 200
        else:
            return jsonify({"error": "Failed to process the BED file"}), 500
    else:
        return jsonify({"error": "Invalid file type"}), 400

# Function to process the BED file from memory and insert into the database
def process_bed_file_in_memory(file):
    conn = create_connection()
    if conn:
        cur = conn.cursor()

        # Use io.BytesIO to handle the file in memory
        file_stream = io.StringIO(file.read().decode('utf-8'))  # Assuming the file is text (e.g., BED format)

        for line in file_stream:
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
                    INSERT INTO bed (chromosome, start, end, peak_score, feature_name)
                    VALUES (%s, %s, %s, %s, %s)
                """, (chromosome, start, end, peak_score, feature_name))

        conn.commit()
        cur.close()
        conn.close()
        return True
    return False

# Function to process the BED file and insert into the database
def process_bed_file(file_path):
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
                        INSERT INTO bed (chromosome, start, end, peak_score, feature_name)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (chromosome, start, end, peak_score, feature_name))

        conn.commit()
        cur.close()
        conn.close()
        return True
    return False

# Function to check if the file is a valid BED file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'bed'}

# Main entry point for Flask app
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
