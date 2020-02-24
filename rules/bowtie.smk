#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd

##### Target rules #####

def get_fasta_sequences(wildcards):
    """
    Get all the FASTA sequences for the multi-FASTA file.
    """
    pick_sequences = checkpoints.entrez_pick_sequences.get(query=wildcards.query)
    sequences = pd.read_csv(pick_sequences.output[0], sep='\t')

    inputs = []

    for key, seq in sequences.iterrows():
        inputs.append('database/{orgname}/{accession}.fasta'.format(orgname=seq['TSeq_orgname'].replace(" ", "."),
                                                                    accession=seq['TSeq_accver']))

    return inputs


rule bowtie_multifasta:
    input:
         get_fasta_sequences
    log:
         "bowtie/{query}/{query}.log"
    output:
         "bowtie/{query}/{query}.fasta"
    script:
          "../scripts/bowtie_multifasta.py"


