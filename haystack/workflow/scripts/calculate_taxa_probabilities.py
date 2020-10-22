#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Evangelos A. Dimopoulos, Evan K. Irving-Pease"
__copyright__ = "Copyright 2020, University of Oxford"
__email__ = "antonisdim41@gmail.com"
__license__ = "MIT"

import numpy as np
import os
import pandas as pd
import sys


def calculate_taxa_probabilities(
    ts_tv_matrix_file, params_file, sample_name, total_fastq_reads, outputfile, submatrices,
):
    """
    Function that calculates the species identification posterior probabilities.
    This function acts as a wrapper around the calculate_probabilities function.
    Function calculate_probabilities actually calculates the probabilities.
    Function calculate_taxa_probabilities acts as a wrapper by providing the right dataset each time.
    "If submatrices" subsample the ts_tv_matrix_file in a for loop way. Could we parallelise this step ?
    """

    assert os.stat(ts_tv_matrix_file).st_size, f"The ts_tv count file is empty {ts_tv_matrix_file}"

    assert os.stat(params_file).st_size, f"The probability model parameters file is empty {params_file}"

    print("all taxa", "\t", sample_name, file=sys.stderr)

    calculate_probabilities(
        ts_tv_matrix_file, params_file, sample_name, total_fastq_reads, outputfile, submatrix="all taxa",
    )


def calculate_probabilities(
    ts_tv_matrix_file, params_file, sample_name, total_fastq_reads, outputfile, submatrix,
):
    total_fastq_reads = float(open(total_fastq_reads, "r").read())

    read_count = len(pd.read_csv(ts_tv_matrix_file, sep=",", usecols=["Read_ID"])["Read_ID"].unique())

    if not read_count:
        print("File is empty, moving on.")

    ts_tv_matrix = pd.read_csv(ts_tv_matrix_file, sep=",", usecols=["Taxon", "Ts", "Tv"])

    model_params = pd.read_json(params_file, orient="index").squeeze()

    mismatch_df = ts_tv_matrix.groupby("Taxon").agg(
        {
            "Ts": lambda num: (sum(num) + ((read_count - num.count()) * (model_params["ts_missing_val"] + 1))),
            "Tv": lambda num: (sum(num) + ((read_count - num.count()) * (model_params["tv_missing_val"] + 1))),
        }
    )

    mismatch_df = mismatch_df.astype({"Ts": float, "Tv": float})

    # mismatch_df = ts_tv_matrix.groupby("Taxon").sum().astype({"Ts": float, "Tv": float})

    mismatch_df.reset_index(inplace=True)

    mismatch_df["Posterior"] = np.nan

    mismatch_df["Read_Count"] = read_count

    mismatch_df["Total_Reads"] = total_fastq_reads

    mismatch_df["Submatrix"] = submatrix

    mismatch_df["Sample"] = sample_name

    for index, row in mismatch_df.iterrows():
        # print row['Taxon'], row['Ts'], row['Vs'], '\n'

        mismatch_t_vec = mismatch_df["Ts"].subtract(row["Ts"]).rpow(model_params["delta_t"])

        # print  Mismatch_df['Ts'].subtract(row['Ts'])

        mismatch_v_vec = mismatch_df["Tv"].subtract(row["Tv"]).rpow(model_params["delta_v"])

        # print Mismatch_df['Vs'].subtract(row['Vs'])

        products = mismatch_t_vec * mismatch_v_vec

        # print products_cur

        denominator_summation = products.sum()

        posterior_row = float(1) / denominator_summation

        # print '\n', denominator_summation, posterior_row

        mismatch_df.iloc[index, 3] = posterior_row

    mismatch_df.sort_values(by="Posterior", ascending=False, inplace=True)

    print(mismatch_df, file=sys.stderr)

    with open(outputfile, "a") as output_handle:
        mismatch_df.to_csv(path_or_buf=output_handle, sep="\t", index=False)


if __name__ == "__main__":
    # redirect all output to the log
    sys.stderr = open(snakemake.log[0], "w")

    calculate_taxa_probabilities(
        ts_tv_matrix_file=snakemake.input[0],
        params_file=snakemake.input[1],
        sample_name=snakemake.wildcards.sample,
        total_fastq_reads=snakemake.input[2],
        outputfile=snakemake.output[0],
        submatrices=snakemake.params["submatrices"],
    )
