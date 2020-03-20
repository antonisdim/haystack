#!/usr/bin/env python
# -*- coding: utf-8 -*-

from multiprocessing import cpu_count

SUBSAMPLE_FIXED_READS = 200000

##### Target rules #####


rule bowtie_index:
    input:
         "{query}/bowtie/{query}.fasta.gz"
    log:
         "{query}/bowtie/{query}_index.log"
    output:
         expand("{{query}}/bowtie/{{query}}.{n}.bt2l", n=[1, 2, 3, 4]),
         expand("{{query}}/bowtie/{{query}}.rev.{n}.bt2l", n=[1, 2])
    shell:
          "bowtie2-build --large-index {input} {wildcards.query}/bowtie/{wildcards.query} &> {log}"


rule bowtie_alignment:
    input:
        fastq=lambda wildcards: config['samples'][wildcards.sample],
        bt2idx="{query}/bowtie/{query}.1.bt2l"
    log:
        "{query}/bam/{sample}.log"
    params:
        index="{query}/bowtie/{query}",
    output:
        "{query}/bam/{sample}_sorted.bam"
    threads:
        cpu_count()
    shell:
         "( bowtie2 -q --very-fast-local --threads {threads} -x {params.index} -U {input.fastq} "
         "| samtools sort -O bam -o {output} ) 2> {log}"


rule remove_duplicates:
    input:
        "{query}/bam/{sample}_sorted.bam"
    log:
        "{query}/bam/{sample}_sorted_rmdup.log"
    output:
        "{query}/bam/{sample}_sorted_rmdup.bam"
    params:
        output="{query}/bam/"
    shell:
        "dedup --merged --input {input} --output {params.output} &> {log}"


rule extract_fastq:
    input:
        "{query}/bam/{sample}_sorted_rmdup.bam"
    log:
        "{query}/fastq/{sample}_mapq.log"
    output:
        "{query}/fastq/{sample}_mapq.fastq.gz"
    params:
        min_mapq = config['min_mapq']
    shell:
        "( samtools view -h -q {params.min_mapq} {input} "
        "| samtools fastq -c 6 - > {output} ) 2> {log}"


rule average_fastq_read_len:
    input:
        "{query}/fastq/{sample}_mapq.fastq.gz"
    log:
        "{query}/fastq/{sample}_mapq_readlen.log"
    output:
        "{query}/fastq/{sample}_mapq.readlen"
    params:
        # TODO you're right seqtk is a better option. Subsampling is required in case the fastq files are massive,
        #  as above 200K reads the average read length doesn't change significantly and it takes far less time.
        size=SUBSAMPLE_FIXED_READS
    shell:
         "seqtk sample {input} {params.size} | seqtk seq -A | grep -v '^>' | "
         "awk '{{count++; bases += length}} END{{print bases/count}}' 1> {output} 2> {log}"
