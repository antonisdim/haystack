#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Evangelos A. Dimopoulos, Evan K. Irving-Pease"
__copyright__ = "Copyright 2020, University of Oxford"
__email__ = "antonisdim41@gmail.com"
__license__ = "MIT"

import argparse
import pandas as pd
import re
import os

from haystack.workflow.scripts.entrez_utils import (
    entrez_esearch,
    entrez_efetch,
)


class ValidationError(Exception):
    pass


class ArgumentCustomFormatter(argparse.HelpFormatter):
    """
    Custom formatter for argparse
    """

    def _get_help_string(self, action):
        message = action.help
        if "%(default)" not in action.help:
            if action.default is not argparse.SUPPRESS and action.default is not None:
                defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                if action.option_strings or action.nargs in defaulting_nargs:
                    message += " (default: %(default)s)"
        return message


class FileType(argparse.FileType):
    """
    Override argparse.FileType to return the filename, rather than an open file handle.
    """

    def __call__(self, string):
        return super().__call__(string).name


class WritablePathType(object):
    """
    Is this a writable path.
    """

    def __call__(self, value):
        from pathlib import Path

        try:
            path = Path(value).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            return value
        except Exception:
            raise argparse.ArgumentTypeError(f"'{value}' is not a valid writable path")


class PositiveIntType(object):
    """
    Is this a positive integer
    """

    def __call__(self, value):
        try:
            if not int(value) > 0:
                raise ValueError()
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"'{value}' is not a valid positive integer"
            )

        return int(value)


class RangeType(object):
    """
    Is this a valid instance of `_type` and within the range [lower, upper]
    """

    def __init__(self, _type, lower, upper):
        self.type = _type
        self.lower = lower
        self.upper = upper

    def __call__(self, value):
        try:
            if not (self.lower <= self.type(value) <= self.upper):
                raise ValueError()
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"'{value}' is not a valid {self.type.__name__} in the range "
                f"({self.lower}, {self.upper})"
            )

        return self.type(value)


class FloatRangeType(RangeType):
    """
    Is this a float() within the given range
    """

    def __init__(self, lower, upper):
        super().__init__(float, lower, upper)


class IntRangeType(RangeType):
    """
    Is this an int() within the given range
    """

    def __init__(self, lower, upper):
        super().__init__(int, lower, upper)


class BoolType(object):
    """
    Is this a valid boolean
    """

    def __call__(self, value):
        if isinstance(value, bool):
            return value
        if value.lower() in ("yes", "true", "t", "y", "1"):
            return True
        elif value.lower() in ("no", "false", "f", "n", "0"):
            return False
        else:
            raise argparse.ArgumentTypeError(f"'{value}' is not a valid boolean")


class JsonType(object):
    """
    Is this a valid JSON string
    """

    def __call__(self, value):
        import json

        try:
            return json.loads(value)
        except json.decoder.JSONDecodeError as error:
            raise argparse.ArgumentTypeError(
                f"'{value}' is not a valid JSON string\n {error}"
            )


class SpreadsheetFileType(FileType):
    """
    Is it a valid user input file
    """

    def __call__(self, string, ncol):
        super().__call__(string)

        file_name = super().__call__(string).name

        # check if the user provided file is empty
        if os.stat(file_name).st_size == 0:
            raise argparse.ArgumentTypeError(
                f"The file '{file_name}' you have provided is empty"
            )

        # check if the provided data are valid
        with open(file_name, "r") as user_input:
            i = 0
            for line in user_input:
                # line number
                i = i + 1
                # split the line
                input_fields = line.split("\t")
                # calculate field number
                input_fields_len = len(input_fields)

                if input_fields_len == 1:
                    raise argparse.ArgumentTypeError(
                        f"The data you have provided in line {i} are not TAB delimited. "
                        f"Please fix the delimiters on that line."
                    )

                if input_fields_len > ncol:
                    raise argparse.ArgumentTypeError(
                        f"The data you have provided in line {i} have more fields than "
                        f"it is required. Please fix that line."
                    )

                if input_fields_len < ncol:
                    raise argparse.ArgumentTypeError(
                        f"Line {i} has less fields than required. Please check the "
                        f"delimiters or if there are missing data."
                    )

                if input_fields_len == 3 and ncol == 3:
                    if not os.path.isfile(input_fields[2]):
                        raise argparse.ArgumentTypeError(
                            f"The path {input_fields[2]} for the custom fasta "
                            f"sequence in line {i} is not valid. Please provide "
                            f"a valid file."
                        )

                if not re.match("^[\w.]+$", input_fields[1]):
                    raise argparse.ArgumentTypeError(
                        f"The accession '{input_fields[1]}' in line '{i}' "
                        f"contains an illegal character"
                    )

        return super().__call__(string).name


class SequenceFileType(SpreadsheetFileType):
    """
    Is this a valid sequence input file.
    """

    def __call__(self, string, ncol):
        return super().__call__(string, ncol).name


class AccessionFileType(SpreadsheetFileType):
    """
    Is this a valid sequence input file.
    """

    def __call__(self, string, ncol):
        return super().__call__(string, ncol).name


class SraAccession(object):
    """Is this a valid SRA accession"""

    def __init__(self, accession):

        # is it a valid sequencing run accession
        if accession[:3] not in ["ERR", "SRR"]:
            raise RuntimeError(f"Invalid SRA accession {config['sra']}.")

        # query the SRA to see if this is a paired-end library or not
        try:
            _, _, id_list = entrez_esearch("sra", config["sra"])
            etree = entrez_efetch("sra", id_list)
            layout = etree.find(".//LIBRARY_LAYOUT/*").tag.lower()
        except Exception:
            raise RuntimeError(f"Unable to resolve the SRA accession {config['sra']}")

        return (accession, layout)


def get_total_paths(
    checkpoints,
    entrez_query,
    with_refseq_rep,
    sequences,
    accessions,
    specific_genera,
    force_accessions,
):
    """
    Get all the individual fasta file paths for the taxa in our database.
    """

    sequences_df = pd.DataFrame()

    if entrez_query:
        pick_sequences = checkpoints.entrez_pick_sequences.get()
        sequences_df = pd.read_csv(pick_sequences.output[0], sep="\t")

        if len(sequences_df) == 0:
            raise RuntimeError("The entrez pick sequences file is empty.")

    if with_refseq_rep:
        refseq_rep_prok = checkpoints.entrez_refseq_accessions.get()
        refseq_genomes = pd.read_csv(refseq_rep_prok.output.refseq_genomes, sep="\t")
        genbank_genomes = pd.read_csv(refseq_rep_prok.output.genbank_genomes, sep="\t")
        assemblies = pd.read_csv(refseq_rep_prok.output.assemblies, sep="\t")
        refseq_plasmids = pd.read_csv(refseq_rep_prok.output.refseq_plasmids, sep="\t")
        genbank_plasmids = pd.read_csv(
            refseq_rep_prok.output.genbank_plasmids, sep="\t"
        )

        if not force_accessions:
            invalid_assemblies = checkpoints.entrez_invalid_assemblies.get()
            invalid_assembly_sequences = pd.read_csv(
                invalid_assemblies.output[0], sep="\t"
            )

            assemblies = assemblies[
                ~assemblies["AccessionVersion"].isin(
                    invalid_assembly_sequences["AccessionVersion"]
                )
            ]

        sources = [
            refseq_genomes,
            genbank_genomes,
            assemblies,
            refseq_plasmids,
            genbank_plasmids,
        ]

        if entrez_query:
            sources.append(sequences_df)

        sequences_df = pd.concat(sources)

    if sequences:
        custom_fasta_paths = pd.read_csv(
            sequences,
            sep="\t",
            header=None,
            names=["species", "AccessionVersion", "path"],
        )

        custom_seqs = custom_fasta_paths[["species", "AccessionVersion"]]
        custom_seqs["AccessionVersion"] = "custom_seq-" + custom_seqs[
            "AccessionVersion"
        ].astype(str)

        sequences_df = sequences_df.append(custom_seqs)

    if accessions:
        custom_accessions = pd.read_csv(
            accessions, sep="\t", header=None, names=["species", "AccessionVersion"],
        )

        sequences_df = sequences_df.append(custom_accessions)

    if specific_genera:
        sequences_df = sequences_df[
            sequences_df["species"].str.contains("|".join(specific_genera))
        ]

    return sequences_df


def normalise_name(taxon):
    """remove unnecessary characters from a taxon name string."""
    return taxon.replace(" ", "_").replace("[", "").replace("]", "").replace("/", "_")


def check_unique_taxa_in_custom_input(accessions, sequences):
    """Checks that custom input files have only one entry per taxon"""

    if accessions != "" and sequences != "":
        custom_fasta_paths = pd.read_csv(
            sequences, sep="\t", header=None, names=["species", "accession", "path"]
        )
        custom_accessions = pd.read_csv(
            accessions, sep="\t", header=None, names=["species", "accession"]
        )

        taxon_acc = custom_accessions["species"].tolist()
        taxon_seq = custom_fasta_paths["species"].tolist()

        if bool(set(taxon_acc) & set(taxon_seq)):
            raise RuntimeError(
                "You have provided the same taxon both in your custom sequences file and your "
                "custom accessions file. Please pick and keep ONLY one entry from both of these files. "
                "You can only have 1 sequence per chosen taxon in your database."
            )


def chunker(seq, size):
    return (seq[pos : pos + size] for pos in range(0, len(seq), size))
