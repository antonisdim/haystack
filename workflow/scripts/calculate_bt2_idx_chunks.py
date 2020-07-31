#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Evangelos A. Dimopoulos, Evan K. Irving-Pease"
__copyright__ = "Copyright 2020, University of Oxford"
__email__ = "antonisdim41@gmail.com"
__license__ = "MIT"

import os
import sys


def calculate_bt2_idx_chunks(mem_resources, mem_rescale_factor, fasta_files, output):
    """Calculate the number of chunks that the db sequences are going to be split into"""

    fasta_paths_random = []
    with open(str(fasta_files), "r") as fin:
        for line in fin:
            fasta_paths_random.append(line.strip())

    chunk_size = float(mem_resources) / float(mem_rescale_factor)
    total_size = 0.0
    chunks = 1

    for fasta_file in fasta_paths_random:
        file_size = os.stat(fasta_file).st_size / (1024 ** 2)

        if file_size >= mem_resources:
            raise RuntimeError(
                "Fasta file {} is bigger than the RAM resources provided. "
                "Unfortunately an index cannot be built.".format(fasta_file)
            )

        if total_size + file_size >= chunk_size:
            total_size = file_size
            chunks += 1
        else:
            total_size += file_size

    with open(output, "w") as outfile:
        print(chunks, file=outfile)


if __name__ == "__main__":
    # redirect all output to the log
    sys.stderr = open(snakemake.log[0], "w")

    calculate_bt2_idx_chunks(
        mem_resources=snakemake.params[1],
        mem_rescale_factor=snakemake.params[2],
        fasta_files=snakemake.input,
        output=snakemake.output[0],
    )
