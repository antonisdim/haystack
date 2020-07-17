#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Evangelos A. Dimopoulos, Evan K. Irving-Pease"
__copyright__ = "Copyright 2020, University of Oxford"
__email__ = "antonisdim41@gmail.com"
__license__ = "MIT"


import sys

import numpy as np
import pandas as pd
from scipy.stats import beta
from scipy.stats import hmean
import os


def calculate_dirichlet_abundances(
    ts_tv_file, pvaluesfile, total_sample_fastq_reads, sample_abundance
):
    """
    Function that calculates the mean posterior abundances of species in metagenomic samples/libraries.
    """

    assert os.stat(ts_tv_file).st_size, "The ts_tv count file is empty {}".format(
        ts_tv_file
    )
    assert os.stat(pvaluesfile).st_size, "The t-test p values file is empty {}".format(
        pvaluesfile
    )
    assert os.stat(
        total_sample_fastq_reads
    ).st_size, "The total fastq reads file is empty {}".format(total_sample_fastq_reads)

    # I calculate the coverage of each taxon from reads in its bam/pileup file. Let's go there

    t_test_vector = (
        pd.read_csv(pvaluesfile, sep="\t", names=["species", "pvalue"])
        .groupby("species")
        .apply(hmean)
        .squeeze()
        .astype("float64")
        .rename("Taxon")
    )
    t_test_vector["Dark_Matter"] = np.nan
    t_test_vector["Grey_Matter"] = np.nan

    ts_tv_matrix = pd.read_csv(
        ts_tv_file, sep=",", usecols=["Taxon", "Read_ID", "Dirichlet_Assignment"]
    )

    # Sum the Dirichlet Assignments per taxon and calculate the Dark Matter reads
    #     from the Dirichlet Assignment column

    ts_tv_group = ts_tv_matrix.groupby("Read_ID").sum().squeeze()
    grey_matter = ts_tv_group.where(ts_tv_group == 0).replace(0, 1).fillna(0)

    a = ts_tv_matrix.groupby("Taxon").sum().squeeze().astype(float)
    a.loc["Grey_Matter"] = grey_matter.sum()

    # Add the non aligned filtered reads count in the Dark Matter category

    total_fastq_reads = float(open(total_sample_fastq_reads, "r").read())
    reads_in_bams = len(ts_tv_matrix["Read_ID"].unique())

    remaining_dark_matter = total_fastq_reads - reads_in_bams

    a.loc["Dark_Matter"] = remaining_dark_matter

    print(a, file=sys.stderr)

    # Perform Alberto's formulas

    b = a.sum()

    posterior_abundance_mean = a.add(1).divide(b + len(a)).sort_values(ascending=False)

    # Prepare the dataframe that is going to be outputted and calculate the rest of the output columns.

    posterior_abundance = posterior_abundance_mean.to_frame().reset_index()

    posterior_abundance.rename(
        columns={"Dirichlet_Assignment": "Mean_Posterior_Abundance"}, inplace=True
    )

    posterior_abundance["95.CI.lower"] = np.nan
    posterior_abundance["95.CI.upper"] = np.nan
    posterior_abundance["Minimum.Read.Num"] = np.nan
    posterior_abundance["Maximum.Read.Num"] = np.nan
    posterior_abundance["Dirichlet.Read.Num"] = np.nan
    posterior_abundance["Fisher.Exact.Pvalue"] = np.nan

    print(t_test_vector.index, file=sys.stderr)

    for idx, row in posterior_abundance.iterrows():
        ai = a.loc[posterior_abundance.iloc[idx, 0]]

        print(ai, file=sys.stderr)

        ci = beta.interval(0.95, ai + 1, b + len(a) - ai - 1)

        print(len(a), file=sys.stderr)

        posterior_abundance.iloc[idx, 2] = ci[0]
        posterior_abundance.iloc[idx, 3] = ci[1]
        posterior_abundance.iloc[idx, 4] = round(ci[0] * b)
        posterior_abundance.iloc[idx, 5] = round(ci[1] * b)
        posterior_abundance.iloc[idx, 6] = a.loc[posterior_abundance.iloc[idx, 0]]
        posterior_abundance.iloc[idx, 7] = t_test_vector.loc[
            posterior_abundance.iloc[idx, 0]
        ]

    # Write the file into a file. Don't need to return anything. Back to anns_pipeline

    with open(sample_abundance, "w") as output_handle:
        posterior_abundance.to_csv(
            path_or_buf=output_handle, sep="\t", index=False, header=True
        )


if __name__ == "__main__":
    # redirect all output to the log
    sys.stderr = open(snakemake.log[0], "w")

    calculate_dirichlet_abundances(
        ts_tv_file=snakemake.input[0],
        pvaluesfile=snakemake.input[1],
        total_sample_fastq_reads=snakemake.input[2],
        sample_abundance=snakemake.output[0],
    )
