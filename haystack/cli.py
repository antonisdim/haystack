#! /usr/bin/env python
"""
Execution script for snakemake workflows.
"""
__author__ = "Evangelos A. Dimopoulos, Evan K. Irving-Pease"
__copyright__ = "Copyright 2020, University of Oxford"
__email__ = "antonisdim41@gmail.com"
__license__ = "MIT"

import os.path
from multiprocessing import cpu_count

import argcomplete
import argparse
import datetime
import os
import pathlib
import snakemake
import sys
import yaml
from Bio import Entrez
from psutil import virtual_memory

from haystack.workflow.scripts.utilities import (
    ValidationError,
    ArgumentCustomFormatter,
    EmailType,
    FileType,
    WritablePathType,
    PositiveIntType,
    FloatRangeType,
    IntRangeType,
    BoolType,
    JsonType,
)

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

MAX_CPU = cpu_count()
MAX_MEM_MB = int(virtual_memory().total / 1024 ** 2)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

CONFIG_DEFAULT = f"{BASE_DIR}/config/config.yaml"
CONFIG_USER = pathlib.Path("~/.haystack/config.yaml").expanduser()

COMMANDS = ["config", "database", "sample", "analyse"]
DATABASE_MODES = ["fetch", "index", "build"]
ANALYSIS_MODES = ["filter", "align", "likelihoods", "probabilities", "abundances", "reads", "mapdamage"]
TAXONOMIC_RANKS = ["genus", "species", "subspecies", "serotype"]

RESTART_TIMES = 3

# maximum concurrent Entrez requests
MAX_ENTREZ_REQUESTS = 3


class Haystack(object):
    """
    Command-line interface for running `haystack`
    """

    def __init__(self):
        parser = argparse.ArgumentParser(
            usage="""haystack <command> [<args>]

The haystack commands are:
   config         Configuration options
   database       Build a database of target species
   sample         Prepare a sample for analysis
   analyse        Analyse a sample against a database
   
""",
        )
        parser.add_argument("command", choices=COMMANDS, help="Command to run")

        # get the CLI arguments
        args = self._parse_args(parser, level=1)

        # load the config files
        self._load_config()

        # TODO drop this setting entirely and replace with OPTIONAL `api_key`
        #      https://www.ncbi.nlm.nih.gov/books/NBK25497/#:~:text=By%20including%20an%20API%20key,.gov%2Faccount%2F)
        # email address is mandatory, unless we are running `haystack config`
        if args.command != "config" and not self.config_user.get("email"):
            print(
                "Before using haystack, please configure your email address.\n"
                "This is a required step for running NCBI queries\n\n"
                "`haystack config --email <address>`"
            )
            exit(1)

        try:
            # call the class method with the name given by `command`
            reval = getattr(self, args.command)()
            exit(reval)

        except ValidationError as error:
            print(f"haystack: error: {error}")
            exit(1)

    @staticmethod
    def _parse_args(parser, level=1):
        """
        Handle the nested-subcommand CLI interface.
        """

        # if we don't have enough arguments, then print the help
        if len(sys.argv) <= level:
            parser.print_help()
            parser.exit()

        # slice the CLI arguments
        argv = sys.argv[1:2] if level == 1 else sys.argv[level:]

        # get the command
        argcomplete.autocomplete(parser)  # TODO autocomplete does not work
        return parser.parse_args(argv)

    def _load_config(self):
        """
        Load the default and user space config files.
        """

        # load the default config
        with open(CONFIG_DEFAULT) as fin:
            self.config_default = yaml.safe_load(fin)

            # resolve relative paths
            self.config_default["cache"] = str(pathlib.Path(self.config_default["cache"]).absolute())

        try:
            # load the user config
            with open(CONFIG_USER) as fin:
                self.config_user = yaml.safe_load(fin)

        except FileNotFoundError:
            # make the config folder (if necessary)
            os.makedirs(os.path.dirname(CONFIG_USER), exist_ok=True)

            self.config_user = dict()

        # merge the config dictionaries (giving precedence to the config_user)
        self.config_merged = {**self.config_default, **self.config_user}

    def config(self):
        """
        Configuration options
        """
        # noinspection PyTypeChecker
        parser = argparse.ArgumentParser(
            prog="haystack config",
            description="Configuration options",
            formatter_class=ArgumentCustomFormatter,
            add_help=False,
        )

        # if the email hasn't been set before then it's mandatory to do it now
        required = parser.add_argument_group("Required arguments") if not self.config_user.get("email") else None
        optional = parser.add_argument_group("Optional arguments")

        # add the help option manually so we can control where it is shown in the menu
        optional.add_argument("-h", "--help", action="help", help="Show this help message and exit")

        # determine which group email belongs in
        group = required or optional

        group.add_argument(
            "--email",
            help="Email address for NCBI identification",
            metavar="<address>",
            type=EmailType("RFC5322"),
            required=not self.config_user.get("email"),
        )

        # TODO add a --clear-cache option
        optional.add_argument(
            "--cache",
            help="Cache folder for storing all the genomes downloaded from NCBI",
            metavar="<path>",
            type=WritablePathType(),
            default=self.config_default["cache"],
        )

        optional.add_argument(
            "--batchsize",
            help="Batch size for fetching records from NCBI",
            type=PositiveIntType(),
            metavar="<int>",
            default=self.config_default["batchsize"],
        )

        optional.add_argument(
            "--mismatch-probability",
            help="Base mismatch probability",
            type=FloatRangeType(0.01, 0.10),
            metavar="<float>",
            default=self.config_default["mismatch_probability"],
        )

        optional.add_argument(
            "--bowtie2-threads",
            help="Number of threads to use for each bowtie2 alignment",
            type=IntRangeType(1, MAX_CPU),
            metavar="<int>",
            default=self.config_default["bowtie2_threads"],
        )

        optional.add_argument(
            "--bowtie2-scaling",
            help="Rescaling factor to keep the bowtie2 mutlifasta index below the maximum memory limit",
            type=FloatRangeType(0, 100),
            metavar="<float>",
            default=self.config_default["bowtie2_scaling"],
        )

        optional.add_argument(
            "--use-conda",
            help="Use conda as a package manger",
            type=BoolType(),
            metavar="<bool>",
            default=self.config_default["use_conda"],
        )

        # get the CLI arguments
        args = self._parse_args(parser, level=2)

        # get the user choices that differ from the defaults
        for key, value in vars(args).items():
            if value != self.config_default.get(key) or (value is not None and self.config_user.get(key) is not None):
                self.config_user[key] = value

        # resolve relative paths
        if self.config_user.get("cache"):
            self.config_user["cache"] = str(pathlib.Path(self.config_user["cache"]).absolute())

        # save the user config
        with open(CONFIG_USER, "w") as fout:
            yaml.safe_dump(self.config_user, fout, default_flow_style=False)

    def database(self):
        """
        Build a database of target species
        """
        # noinspection PyTypeChecker
        parser = argparse.ArgumentParser(
            prog="haystack database",
            description="Build a database of target species",
            formatter_class=ArgumentCustomFormatter,
            add_help=False,
        )

        required = parser.add_argument_group("Required arguments")

        required.add_argument(
            "--mode",
            help="Database creation mode for haystack [%(choices)s]",
            metavar="<mode>",
            choices=DATABASE_MODES,
            required=True,
        )

        required.add_argument(
            "--output",
            help="Path to the database output directory",
            metavar="<path>",
            dest="db_output",
            type=WritablePathType(),
            required=True,
        )

        choice = parser.add_argument_group("Required choice")

        # TODO how can we validate these queries?
        choice.add_argument(
            "--query",
            help="Database query in the NCBI query language. "
            "Please refer to the documentation for assistance with constructing a valid query.",
            metavar="<query>",
        )

        choice.add_argument(
            "--query-file",
            help="File containing a database query in the NCBI query language.",
            metavar="<path>",
            type=FileType("r"),
        )

        # TODO validate that this is 2-column and tab delimited
        choice.add_argument(
            "--accessions",
            help="Tab delimited file containing one record per row: the name of the taxon, "
            "and a valid NCBI accession code from the nucleotide, assembly or WGS databases.",
            metavar="<path>",
            type=FileType("r"),
        )

        # TODO validate that this is 3-column and tab delimited
        choice.add_argument(
            "--sequences",
            help="Tab delimited file containing one record per row: the name of the taxon, a user defined "
            "accession code, and the path to the fasta file (optionally compressed).",
            metavar="<path>",
            type=FileType("r"),
        )

        choice.add_argument(
            "--refseq-rep",
            help="Include all prokaryotic species (excluding strains) from the representative RefSeq DB",
            action="store_true",
        )

        optional = parser.add_argument_group("Optional arguments")

        optional.add_argument(
            "--rank",
            help="Taxonomic rank to perform the identifications on [%(choices)s]",
            metavar="<rank>",
            choices=TAXONOMIC_RANKS,
            default=self.config_default["rank"],
        )

        optional.add_argument(
            "--genera",
            help="List of genera to restrict the abundance calculations.",
            metavar="<genus>",
            nargs="+",
            default=None,
        )

        optional.add_argument(
            "--mtDNA",
            help="For eukaryotes, download mitochondrial genomes only. "
            "Not to be used with --refseq-rep or queries containing prokaryotes",
            action="store_true",
        )

        optional.add_argument(
            "--seed",
            help="Random seed for database indexing",
            metavar="<int>",
            type=int,
            default=self.config_default["seed"],
        )

        # add the common arguments
        self._common_arguments(parser)

        # get the CLI arguments
        args = self._parse_args(parser, level=2)

        # must specify at least one source for the database
        if not (args.refseq_rep or args.query or args.query_file or args.accessions or args.sequences):
            raise ValidationError(
                "Please specify at least one of --refseq-rep, --query, --query-file, --accessions or --sequences"
            )

        if args.mtDNA and args.refseq_rep:
            raise ValidationError("Please specify either `--mtDNA` or `--refseq-rep` but not both.")

        if args.query and args.query_file:
            raise ValidationError("Please specify either `--query <query>` or `--query-file <path>` but not both.")

        if args.query_file:
            # load the query file
            with open(args.query_file) as fin:
                args.query = fin.read().strip()

            if not args.query:
                raise ValidationError(f"The query file '{args.query_file}' is empty.")

        # resolve relative paths
        args.db_output = os.path.abspath(args.db_output)

        # cast all `None` paths as "" or ele smk complains when parsing the rules
        args.query_file = args.query_file or ""
        args.accessions = args.accessions or ""
        args.sequences = args.sequences or ""

        # add all command line options to the merged config
        config = {**self.config_merged, **vars(args)}

        # TODO if build, confirm details match! do the same for sample and analyse
        config_fetch = os.path.join(args.db_output, "database_fetch_config.yaml")
        config_build = os.path.join(args.db_output, "database_build_config.yaml")

        target_list = list()

        if args.mode == "fetch":
            # TODO can this be replaced with a single target? and the conditional logic moved into an input function
            if args.query:
                target_list.append("bowtie/entrez_query.fasta.gz")
            if args.refseq_rep:
                target_list.append("bowtie/refseq_prok.fasta.gz")
            if args.sequences:
                target_list.append("bowtie/custom_seqs.fasta.gz")
            if args.accessions:
                target_list.append("bowtie/custom_acc.fasta.gz")

            with open(config_fetch, "w") as fout:
                yaml.safe_dump(config, fout, default_flow_style=False)

        elif args.mode == "index":
            target_list.append("bowtie/bowtie_index.done")

            try:
                with open(config_fetch, "r") as fin:
                    config = yaml.safe_load(fin)
            except FileNotFoundError:
                raise ValidationError(
                    "Please run haystack `database --mode fetch` before attempting to index the database."
                )

        elif args.mode == "build":
            target_list.append("idx_database.done")
            target_list.append("bowtie/bowtie_index.done")

            if os.path.exists(config_fetch):
                raise ValidationError(
                    "Please run haystack `database --mode index` as the database has already been fetched."
                )

            with open(config_build, "w") as fout:
                yaml.safe_dump(config, fout, default_flow_style=False)

        config["mtDNA"] = str(args.mtDNA).lower()

        target_list = [os.path.join(args.db_output, target) for target in target_list]
        snakefile = os.path.join(BASE_DIR, "workflow/database.smk")

        recode = self._run_snakemake(snakefile, args, config, target_list)

        if recode == 0 and not args.unlock:
            print("Please run `haystack database --mode index` after this step.")

        return recode

    def sample(self):
        """
        Prepare a sample for analysis
        """
        # noinspection PyTypeChecker
        parser = argparse.ArgumentParser(
            prog="haystack sample",
            description="Prepare a sample for analysis",
            formatter_class=ArgumentCustomFormatter,
            add_help=False,
        )

        required = parser.add_argument_group("Required arguments")

        # TODO do we need this?
        required.add_argument(
            "--sample-prefix", help="Sample prefix for all the future analysis.", metavar="<prefix>",
        )

        required.add_argument(
            "--output",
            help="Path to the sample output directory",
            metavar="<path>",
            dest="sample_output_dir",
            type=WritablePathType(),
            required=True,
        )

        choice = parser.add_argument_group("Required choice")

        choice.add_argument(
            "--fastq",
            help="Single-end fastq input file (optionally compressed).",
            metavar="<path>",
            type=FileType("r"),
        )

        choice.add_argument(
            "--fastq-r1", help="Paired-end forward strand (R1) fastq input file.", metavar="<path>", type=FileType("r"),
        )

        choice.add_argument(
            "--fastq-r2", help="Paired-end reverse strand (R2) fastq input file.", metavar="<path>", type=FileType("r"),
        )

        # TODO make an SraType that validates the code and returns the tuple (accession, paired|single)
        choice.add_argument(
            "--sra", help="Download fastq input from the SRA database", metavar="<accession>",
        )

        optional = parser.add_argument_group("Optional arguments")

        optional.add_argument(
            "--collapse",
            help="Collapse overlapping paired-end reads, e.g. for aDNA",
            type=BoolType(),
            metavar="<bool>",
            default=self.config_default["collapse"],
        )

        optional.add_argument(
            "--trim-adapters",
            help="Automatically trim sequencing adapters from fastq input",
            type=BoolType(),
            metavar="<bool>",
            default=self.config_default["trim_adapters"],
        )

        # TODO does this do anything?
        optional.add_argument(
            "--adaperremoval-flags",
            help="Pass additional flags to `AdapterRemoval`",
            metavar="'<json>'",
            type=JsonType(),
        )

        # add the common arguments
        self._common_arguments(parser)

        # get the CLI arguments
        args = self._parse_args(parser, level=2)

        # must specify exactly one source for the sample
        if bool(args.fastq) + (bool(args.fastq_r1) and bool(args.fastq_r2)) + bool(args.sra) != 1:
            raise ValidationError("Please specify either --sra or --fastq, or both --fastq-r1 and --fastq-r2.")

        if args.collapse and not (args.fastq_r1 and args.fastq_r2):
            raise ValidationError("Collapse can only be used with --fastq-r1 and --fastq-r2.")

        if not args.sample_prefix and not args.sra:
            raise ValidationError("Please provide a --sample-prefix name.")

        # resolve relative paths
        args.sample_output_dir = os.path.abspath(args.sample_output_dir)

        # cast all `None` paths as "" or ele smk complains when parsing the rules
        args.fastq = args.fastq or ""
        args.fastq_r1 = args.fastq_r1 or ""
        args.fastq_r2 = args.fastq_r2 or ""

        # add all command line options to the merged config
        config = {**self.config_merged, **vars(args)}

        # TODO are these flags really necessary?
        #      why not combine into one single config value? (e.g. config["mode"] = SE|PE|COLLAPSE
        config["SE"] = not (args.fastq_r1 and args.fastq_r2)
        config["PE_ANCIENT"] = not config["SE"] and args.collapse
        config["PE_MODERN"] = not config["SE"] and not args.collapse

        # TODO rethink this...
        if args.sra:
            if args.sample_prefix:
                raise ValidationError("--sample-prefix cannot be used with and SRA accession.")

            # use the SRA accession as the sample prefix
            config["sample_prefix"] = args.sra

            # TODO refactor this out
            # get paired/single status of the accession
            Entrez.email = config["email"]
            sra_id = Entrez.read(Entrez.esearch(db="sra", term=config["sra"]))["IdList"]
            if "paired" in str(Entrez.read(Entrez.esummary(db="sra", id=sra_id))).lower():
                if config["collapse"]:
                    config["PE_ANCIENT"] = True
                else:
                    config["PE_MODERN"] = True

                config["fastq_r1"] = f"sra_data/PE/{config['sra']}_R1.fastq.gz"
                config["fastq_r2"] = f"sra_data/PE/{config['sra']}_R1.fastq.gz"

            else:
                config["SE"] = True
                config["fastq"] = f"sra_data/SE/{config['sra']}.fastq.gz"

        target_list = list()
        target_list.append(f"fastq_inputs/meta/{config['sample_prefix']}.size")

        if config["trim_adapters"]:
            if config["PE_MODERN"]:
                target_list.append(f"fastq_inputs/PE_mod/{config['sample_prefix']}_R1_adRm.fastq.gz")
            elif config["PE_ANCIENT"]:
                target_list.append(f"fastq_inputs/PE_anc/{config['sample_prefix']}_adRm.fastq.gz")
            elif config["SE"]:
                target_list.append(f"fastq_inputs/SE/{config['sample_prefix']}_adRm.fastq.gz")

        config_sample = os.path.join(args.sample_output_dir, "sample_config.yaml")

        with open(config_sample, "w") as fout:
            yaml.safe_dump(config, fout, default_flow_style=False)

        target_list = [os.path.join(args.sample_output_dir, target) for target in target_list]
        snakefile = os.path.join(BASE_DIR, "workflow/sample.smk")

        return self._run_snakemake(snakefile, args, config, target_list)

    def analyse(self):
        """
        Analyse a sample against a database
        """
        # noinspection PyTypeChecker
        parser = argparse.ArgumentParser(
            prog="haystack analyse",
            description="Analyse a sample against a database",
            formatter_class=ArgumentCustomFormatter,
            add_help=False,
        )

        required = parser.add_argument_group("Required arguments")

        required.add_argument(
            "--mode",
            help="Analysis mode for the selected sample [%(choices)s]",
            metavar="<mode>",
            choices=ANALYSIS_MODES,
            required=True,
        )

        required.add_argument(
            "--database",
            help="Path to the database output directory",
            metavar="<path>",
            dest="db_output",
            type=WritablePathType(),
            required=True,
        )

        required.add_argument(
            "--sample",
            help="Path to the sample output directory",
            metavar="<path>",
            dest="sample_output_dir",
            type=WritablePathType(),
            required=True,
        )

        required.add_argument(
            "--output",
            help="Path to the analysis output directory",
            metavar="<path>",
            dest="analysis_output_dir",
            type=WritablePathType(),
            required=True,
        )

        optional = parser.add_argument_group("Optional arguments")

        optional.add_argument(
            "--genera",
            help="List of genera to restrict the abundance calculations.",
            metavar="<genus>",
            nargs="+",
            default=[],
        )

        # TODO shorten this name! (e.g. --min-prob)
        optional.add_argument(
            "--read-probability-threshold",
            help="Minimum posterior probability to assign an aligned read to a given species",
            type=FloatRangeType(0, 100),
            metavar="<float>",
            default=self.config_default["read_probability_threshold"],
        )

        # TODO do we also need an option for the mean posterior abundance?

        # add the common arguments
        self._common_arguments(parser)

        # get the CLI arguments
        args = self._parse_args(parser, level=2)

        # resolve relative paths
        args.db_output = os.path.abspath(args.db_output)
        args.sample_output_dir = os.path.abspath(args.sample_output_dir)
        args.analysis_output_dir = os.path.abspath(args.analysis_output_dir)

        config_fetch = os.path.join(args.db_output, "database_fetch_config.yaml")
        config_build = os.path.join(args.db_output, "database_build_config.yaml")
        config_sample = os.path.join(args.sample_output_dir, "sample_config.yaml")

        try:
            # load the database config
            database_config_file = config_fetch if os.path.exists(config_fetch) else config_build
            with open(database_config_file, "r") as fin:
                database_config = yaml.safe_load(fin)
        except FileNotFoundError:
            raise ValidationError(
                "The database has not been built correctly. Please rebuild the database using `haystack database`"
            )

        try:
            # load the sample config
            with open(config_sample, "r") as fin:
                sample_config = yaml.safe_load(fin)
        except FileNotFoundError:
            raise ValidationError(
                "The sample has not been prepared correctly. Please pre-process the samples using `haystack sample`"
            )

        # add all command line options to the merged config
        config = {**self.config_merged, **database_config, **sample_config, **vars(args)}

        target_list = list()

        if args.mode == "filter":
            if config["PE_MODERN"]:
                target_list.append(f"fastq/PE/{config['sample_prefix']}_mapq_pair.readlen")
            else:
                target_list.append(f"fastq/SE/{config['sample_prefix']}_mapq.readlen")

        elif args.mode == "align":
            target_list.append(f"sigma/{config['sample_prefix']}_alignments.done")

        elif args.mode == "likelihoods":
            target_list.append(
                f"probabilities/{config['sample_prefix']}/{config['sample_prefix']}_likelihood_ts_tv_matrix.csv"
            )

        elif args.mode == "probabilities":
            target_list.append(
                f"probabilities/{config['sample_prefix']}/{config['sample_prefix']}_posterior_probabilities.tsv"
            )

        elif args.mode == "abundances":
            target_list.append(
                f"probabilities/{config['sample_prefix']}/{config['sample_prefix']}_posterior_abundance.tsv"
            )

        elif args.mode == "reads":
            target_list.append("/dirichlet_reads/{config['sample_prefix']}_dirichlet_reads.done")

        elif args.mode == "mapdamage":
            target_list.append(f"mapdamage/{config['sample_prefix']}_mapdamage.done")

        config_analysis = os.path.join(args.analysis_output_dir, config["sample_prefix"] + "_config.yaml")

        with open(config_analysis, "w") as fout:
            yaml.safe_dump(config, fout, default_flow_style=False)

        target_list = [os.path.join(args.analysis_output_dir, target) for target in target_list]
        snakefile = os.path.join(BASE_DIR, "workflow/analyse.smk")

        return self._run_snakemake(snakefile, args, config, target_list)

    def _common_arguments(self, parser):
        """
        Add the common arguments shared by the `database`, `sample` and `analyse` commands
        """
        common = parser.add_argument_group("Common arguments")

        # add the help option manually so we can control where it is shown in the menu
        common.add_argument("-h", "--help", action="help", help="Show this help message and exit")

        common.add_argument(
            "--cores",
            help="Maximum number of CPU cores to use",
            metavar="<int>",
            type=IntRangeType(1, MAX_CPU),
            default=MAX_CPU if self.config_default["cores"] == "all" else self.config_default["cores"],
        )

        common.add_argument(
            "--mem",
            help="Maximum memory (MB) to use",
            type=IntRangeType(1024, MAX_MEM_MB),
            default=MAX_MEM_MB if self.config_default["mem"] == "all" else self.config_default["mem"],
            metavar="<int>",
        )

        common.add_argument(
            "--unlock", help="Unlock the output directory following a crash or hard restart", action="store_true",
        )

        common.add_argument(
            "--debug", help="Enable debugging mode", action="store_true",
        )

        common.add_argument(
            "--snakemake",
            help="Pass additional flags to the `snakemake` scheduler.",
            metavar="'<json>'",
            type=JsonType(),
        )

    @staticmethod
    def _run_snakemake(snakefile, args, config, target_list):
        """
        Helper function for running the snakemake workflow
        """
        print("HAYSTACK\n")
        print(f"Date: {datetime.datetime.now()}\n")

        config["workflow_dir"] = os.path.join(BASE_DIR, "workflow")

        print("Config parameters:\n")
        params = config if args.debug else vars(args)

        for key, value in params.items():
            if value or args.debug:
                print(f" {key}: {value}")
        print("\n")

        if args.debug:
            print("Target files:\n")
            for target in target_list:
                print(" " + target)
            print("\n")

        # get any extra snakemake params
        smk_params = config.pop("snakemake") or {}

        success = snakemake.snakemake(
            snakefile,
            config=config,
            targets=target_list,
            printreason=args.debug,
            printshellcmds=args.debug,
            cores=int(args.cores),
            keepgoing=(not args.debug),
            restart_times=0 if args.debug else RESTART_TIMES,
            unlock=args.unlock,
            show_failed_logs=args.debug,
            resources={"entrez_api": MAX_ENTREZ_REQUESTS},
            use_conda=config["use_conda"],
            verbose=args.debug,
            keep_incomplete=args.debug,
            force_incomplete=(not args.debug),
            **smk_params,
        )

        # TODO should we delete the `.snakemake` metadata directory?

        # translate "success" into shell exit code of 0
        return 0 if success else 1


if __name__ == "__main__":
    Haystack()
