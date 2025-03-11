# ChipSQLInterface

ChipSQLInterface is a system for defining and deploying Apptainer images using an existing Apptainer installation and Make.

## Overview
The primary purpose of this system is to provide an interface to a SQLite database, allowing integration with OpenOffice or Microsoft's SQL database tools. Additionally, it deploys a server that enables users to upload GTF and BED files to the database and run a query to select genes close to the bed entries.

## Build Instructions
To build the Apptainer image, you need both **Apptainer** and **Make** installed. Follow these steps:

```sh
git pull https://github.com/stela2502/ChipSQLInterface.git
cd ChipSQLInterface
make restart build deploy
```

By default, this process deploys the image as a Slurm module on the COSMOS-Sens system, although this deploay traget is tailored for my development setup. You likely need to adjust the `deploy` target in the Makefile to fit your setup or use the image locally.

### Running the Interface
Two Bash scripts facilitate interaction with the environment:
- **`./shell.sh`** – Loads the sandbox environment.
- **`./runs.sh`** – Loads the built image.

Other server interaction scripts are located in the `bin` directory:

```sh
bin/ChipSQLInterface <path>
```
This command starts the image with `<path>` as the database directory, launching a web interface for uploading BED files. This is the recommended way to start this server as this will also create the necessary files if they are missing. The main database folder needs to exist before running this script.


## Usage
### Starting the Server
On COSMOS-Sens, load the module using:

```sh
module use /scale/gr01/shared/common/modules
ml ChipSQLInterface/1.0
```

To start the server, provide an empty folder where the database will be built:

```sh
ChipSQLInterface <your database folder>
```

This command starts a web server for uploading a GTF file and multiple BED files. The server allows querying all BED files collectively and filtering genes based on their proximity to BED regions.
The startup script will write the server location into STDERR on startup.

### Uploading a GTF Genome Annotation File
You can upload a single GTF file to the database, ensuring it contains **gene  entries**. If needed, download a compatible GTF file from [GENCODE](https://www.gencodegenes.org/). Make sure the GTF matches your BED file's genome version.

To upload:
1. Select an **unzipped** GTF file.
2. Click the **Upload** button below the file selection box.

If the upload fails, delete the `genome.db` file and reload the page.

### Uploading a BED File
BED files describe genomic regions and are typically results from e.g. ChIP-seq analyses. This tool allows uploading multiple BED files for streamlined downstream analysis.

#### Uploading Process:
1. Enter a new **experiment name** or select an existing experiment.
2. Choose the corresponding BED file.
3. Click the **Upload** button.

After uploading, the main web page displays the total peak count per experiment.

## Gene-BED Association
This tool helps identify genes near BED file entries by comparing the closest BED entry edge to gene start positions.

You can define a **distance threshold** for gene proximity. Clicking **Download** triggers a query similar to this:

```sql
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
        WHEN g.start > b.stop THEN g.start - b.stop
        WHEN g.stop < b.start THEN b.start - g.stop
        ELSE 0
    END AS distance
FROM genes g
JOIN bed b ON g.chromosome = b.chromosome
JOIN experiments e ON b.experiment_id = e.id
WHERE (g.start - ? <= b.stop AND g.stop + ? >= b.start)
ORDER BY g.chromosome, g.start;
```

The **?** placeholders are replaced with your specified threshold. The results can be downloaded and accessed via external tools like **Libreoffice Calc or Excel**. Of casue you can also try your luck with the database itself. It should be rather simple to upload Statistic results into this database and restrict the returned genes to genes passing a certain cutoff.



