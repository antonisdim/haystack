Command Line Interface
======================

``haystac config``
------------------

Optional arguments::

  -h, --help          Show this help message and exit
  --cache <path>      Cache folder for storing genomes downloaded from NCBI
                      and other shared data (default:
                      /home/antony/haystac/cache)
  --clear-cache       Clear the contents of the cache folder, and delete the
                      folder itself (default: False)
  --api-key <code>    Personal NCBI API key (increases max concurrent requests
                      from 3 to 10,
                      https://www.ncbi.nlm.nih.gov/account/register/)
  --use-conda <bool>  Use conda as a package manger (default: False)

``haystac database``
--------------------

Required arguments::

  --mode <mode>         Database creation mode for haystac [fetch, index,
                        build]
  --output <path>       Path to the database output directory

Required choice::

  --query <query>       Database query in the NCBI query language. Please
                        refer to the documentation for assistance with
                        constructing a valid query.
  --query-file <path>   File containing a database query in the NCBI query
                        language.
  --accessions-file <path>
                        Tab delimited file containing one record per row: the
                        name of the taxon, and a valid NCBI accession code
                        from the nucleotide, assembly or WGS databases.
  --sequences-file <path>
                        Tab delimited file containing one record per row: the
                        name of the taxon, a user defined accession code, and
                        the path to the fasta file (optionally compressed).
  --refseq-rep <table>  Use one of the RefSeq curated tables to construct a
                        DB. Includes all prokaryotic species (excluding
                        strains) from the representative RefSeq DB, or all the
                        species and strains from the viruses DB, or all the
                        species and subspecies from the eukaryotes DB. If
                        multiple accessions exist for a given species/strain,
                        the first pair of species/accession is kept. Available
                        RefSeq tables to use [prokaryote_rep, viruses,
                        eukaryotes].

Optional arguments::

  --force-accessions    Disable validation checks for 'anomalous' assembly
                        flags in NCBI (default: False)
  --exclude-accessions <accession> [<accession> ...]
                        List of NCBI accessions to exclude. (default: [])
  --resolve-accessions  Pick the first accession when two accessions for a
                        taxon can be found in user provided input files
                        (default: False)
  --bowtie2-scaling <float>
                        Rescaling factor to keep the bowtie2 mutlifasta index
                        below the maximum memory limit (default: 25.0)
  --rank <rank>         Taxonomic rank to perform the identifications on
                        [genus, species, subspecies, serotype] (default:
                        species)
  --genera <genus> [<genus> ...]
                        List of genera to restrict the abundance calculations.
  --mtDNA               For eukaryotes, download mitochondrial genomes only.
                        Not to be used with --refseq-rep or queries containing
                        prokaryotes (default: False)
  --seed <int>          Random seed for database indexing

Common arguments::

  -h, --help            Show this help message and exit
  --cores <int>         Maximum number of CPU cores to use (default: MAX_CPUs)
  --mem <int>           Maximum memory (MB) to use (default: MAX_MEM)
  --unlock              Unlock the output directory following a crash or hard
                        restart (default: False)
  --debug               Enable debugging mode (default: False)
  --snakemake '<json>'  Pass additional flags to the `snakemake` scheduler..

``haystac sample``
------------------

Required arguments::

  --output <path>       Path to the sample output directory

Required choice::

  --fastq <path>        Single-end fastq input file (optionally compressed).
  --fastq-r1 <path>     Paired-end forward strand (R1) fastq input file.
  --fastq-r2 <path>     Paired-end reverse strand (R2) fastq input file.
  --sra <accession>     Download fastq input from the SRA database

Optional arguments::

  --collapse <bool>     Collapse overlapping paired-end reads, e.g. for aDNA
                        (default: False)
  --trim-adapters <bool>
                        Automatically trim sequencing adapters from fastq
                        input (default: True)

Common arguments::

  -h, --help            Show this help message and exit
  --cores <int>         Maximum number of CPU cores to use (default: MAX_CPUs)
  --mem <int>           Maximum memory (MB) to use (default: MAX_MEM)
  --unlock              Unlock the output directory following a crash or hard
                        restart (default: False)
  --debug               Enable debugging mode (default: False)
  --snakemake '<json>'  Pass additional flags to the ``snakemake`` scheduler.

``haystac analyse``
-------------------

Required arguments::

  --mode <mode>         Analysis mode for the selected sample [filter, align,
                        likelihoods, probabilities, abundances, reads,
                        mapdamage]
  --database <path>     Path to the database output directory
  --sample <path>       Path to the sample output directory
  --output <path>       Path to the analysis output directory

Optional arguments::

  --genera <genus> [<genus> ...]
                        List of genera to restrict the abundance calculations
                        (default: [])
  --min-prob <float>    Minimum posterior probability to assign an aligned
                        read to a given species (default: 0.75)
  --mismatch-probability <float>
                        Base mismatch probability (default: 0.05)

Common arguments::

  -h, --help            Show this help message and exit
  --cores <int>         Maximum number of CPU cores to use (default: MAX_CPUs)
  --mem <int>           Maximum memory (MB) to use (default: MAX_MEM)
  --unlock              Unlock the output directory following a crash or hard
                        restart (default: False)
  --debug               Enable debugging mode (default: False)
  --snakemake '<json>'  Pass additional flags to the `snakemake` scheduler.
