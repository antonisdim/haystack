#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Evangelos A. Dimopoulos, Evan K. Irving-Pease"
__copyright__ = "Copyright 2020, University of Oxford"
__email__ = "antonisdim41@gmail.com"
__license__ = "MIT"


rule adapterremoval_single_end:
    input:
        fastq=config["fastq"],
    log:
        config["sample_output_dir"] + "/fastq_inputs/SE/{accession}_adRm.log",
    output:
        config["sample_output_dir"] + "/fastq_inputs/SE/{accession}_adRm.fastq.gz",
    benchmark:
        repeat("benchmarks/adapterremoval_single_end_{accession}.benchmark.txt", 1)
    message:
        "Trimming sequencing adapters from file {input.fastq}."
    conda:
        "../envs/adapterremoval.yaml"
    params:
        basename=config["sample_output_dir"] + "/fastq_inputs/SE/{accession}",
    shell:
        "(AdapterRemoval"
        "   --file1 {input}"
        "   --basename {params.basename} "
        "   --gzip "
        "   --minlength 15 "
        "   --trimns && "
        " mv {params.basename}.truncated.gz {output}"
        ") 2> {log}"


rule adapterremoval_paired_end_ancient:
    input:
        fastq_r1=config["fastq_r1"],
        fastq_r2=config["fastq_r2"],
    log:
        config["sample_output_dir"] + "/fastq_inputs/PE_ANCIENT/{accession}_adRm.log",
    output:
        config["sample_output_dir"] + "/fastq_inputs/PE_ANCIENT/{accession}_adRm.fastq.gz",
    benchmark:
        repeat("benchmarks/adapterremoval_paired_end_ancient_{accession}.benchmark.txt", 1)
    message:
        "Trimming sequencing adapters and collapsing reads from files {input.fastq_r1} and {input.fastq_r2}."
    conda:
        "../envs/adapterremoval.yaml"
    params:
        basename=config["sample_output_dir"] + "/fastq_inputs/PE_ANCIENT/{accession}",
    shell:
        "(AdapterRemoval"
        "   --file1 {input.fastq_r1} "
        "   --file2 {input.fastq_r2} "
        "   --basename {params.basename} "
        "   --gzip "
        "   --collapse-deterministic "
        "   --minlength 15 "
        "   --trimns && "
        " cat {params.basename}.collapsed.gz {params.basename}.collapsed.truncated.gz 1> {output} && "
        " unlink {params.basename}.collapsed.gz && "
        " unlink {params.basename}.collapsed.truncated.gz "
        ") 2> {log}"


rule adapterremoval_paired_end_modern:
    input:
        fastq_r1=config["fastq_r1"],
        fastq_r2=config["fastq_r2"],
    log:
        config["sample_output_dir"] + "/fastq_inputs/PE_MODERN/{accession}_adRm.log",
    output:
        fastq_r1=config["sample_output_dir"] + "/fastq_inputs/PE_MODERN/{accession}_R1_adRm.fastq.gz",
        fastq_r2=config["sample_output_dir"] + "/fastq_inputs/PE_MODERN/{accession}_R2_adRm.fastq.gz",
    benchmark:
        repeat("benchmarks/adapterremoval_paired_end_modern_{accession}.benchmark.txt", 1)
    message:
        "Trimming sequencing adapters from files {input.fastq_r1} and {input.fastq_r2}."
    conda:
        "../envs/adapterremoval.yaml"
    params:
        basename=config["sample_output_dir"] + "/fastq_inputs/PE_MODERN/{accession}",
    shell:
        "(AdapterRemoval"
        "   --file1 {input.fastq_r1}"
        "   --file2 {input.fastq_r2} "
        "   --basename {params.basename}"
        "   --gzip "
        "   --minlength 15 "
        "   --trimns &&"
        " mv {params.basename}.pair1.truncated.gz {output.fastq_r1} && "
        " mv {params.basename}.pair2.truncated.gz {output.fastq_r2} "
        ") 2> {log}"
