# ChipSQLInterface

Is an Apptainer definition and deploy system that sets up an apptainer image using a current apptainer installation and make.

The main usage of this system is to provide an interface to a postgress database folder that can be linked to an openoffice or whatever Microsoft has for interacting with a SQL database.
But it also deploys a server that can be used to upload bed files to the database.

# Build

To build the apptainer image you of casue need apptainer, but as this is a make based system you also need make.

```

git pull https://github.com/stela2502/ChipSQLInterface.git
cd ChipSQLInterface

make restart build deploy
```

This logics as is would deploy the image as a slurm module on our COSMOS-Sens system.
You need to adjust the make target "deploy" to fit to your system,
or you just use the image in place.

There are two bash scripts that load either the sandbox (./shell.sh) or the built image (./runs.sh).
The other scripts to interact with the server are in the bin folder.

```
bin/ChipSQLInterface <path> 
```

Would start the image using the path as the database directory.
This would interact with the database and span up a web interface you can use to upload bed files.

```
bin/start_from_gtf <gtf> <path>
```

This script would initialize the database in the path and import the gene and transcript information into the databasep preparing it to allow for uploading bed files and connecting for analysis.

# Usage

Will be updated as soon as it is usable ;-)


