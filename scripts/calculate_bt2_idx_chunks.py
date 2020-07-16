#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from psutil import virtual_memory

MAX_MEM_MB = virtual_memory().total / (1024 ** 2)


def calculate_bt2_idx_chunks(
    mem_resources, mem_rescaling_factor, input_file_list, output
):
    """Calculate the number of chunks that the db sequences are going to be split into"""

    mem_resources_mb = float(mem_resources)

    if not mem_resources_mb:
        mem_resources_mb = MAX_MEM_MB

    total_file_size = 0
    input_file_list = [i for i in str(input_file_list).split()]
    scaling_factor = mem_rescaling_factor

    chunk_num = 1

    for input_file in input_file_list:

        size_to_be = total_file_size + os.stat(input_file).st_size / float(1024 ** 2)

        if size_to_be <= mem_resources_mb / float(scaling_factor):
            total_file_size += os.stat(input_file).st_size / float(1024 ** 2)

        elif size_to_be > mem_resources_mb / float(scaling_factor):
            total_file_size = 0
            chunk_num += 1
            total_file_size += os.stat(input_file).st_size / float(1024 ** 2)

    with open(output, "w") as outfile:
        print(chunk_num, file=outfile)


if __name__ == "__main__":
    # redirect all output to the log
    sys.stderr = open(snakemake.log[0], "w")

    calculate_bt2_idx_chunks(
        mem_resources=snakemake.params[1],
        mem_rescaling_factor=snakemake.params[2],
        input_file_list=snakemake.input,
        output=snakemake.output[0],
    )