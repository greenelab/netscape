"""
Adapted from:
https://github.com/greenelab/BioBombe/blob/master/2.sequential-compression/scripts/train_models_given_z.py

"""
import os
import argparse
import logging
import numpy as np
import pandas as pd

import config as cfg
from data_models import DataModel
import utilities.data_utilities as du

def shuffle_train_genes(train_df):
    # randomly permute genes of each sample in the rnaseq matrix
    shuf_df = train_df.apply(lambda x:
                             np.random.permutation(x.tolist()),
                             axis=1)

    # Setup new pandas dataframe
    shuf_df = pd.DataFrame(shuf_df, columns=['gene_list'])
    shuf_df = pd.DataFrame(shuf_df.gene_list.values.tolist(),
                           columns=rnaseq_train_df.columns,
                           index=rnaseq_train_df.index)
    return shuf_df

p = argparse.ArgumentParser()
p.add_argument('-a', '--algorithm', default=None,
               help='which transform to run, default runs all\
                     of the transforms that are implemented',
               choices=DataModel.list_algorithms())
p.add_argument('-k', '--num_components', type=int,
               help='dimensionality of z')
p.add_argument('-n', '--num_seeds', type=int, default=5,
               help='number of different seeds to run on current data')
p.add_argument('-m', '--subset_mad_genes', type=int,
               default=cfg.num_features_raw,
               help='subset num genes based on mean absolute deviation')
p.add_argument('-o', '--models_dir', default=cfg.models_dir,
               help='where to save the output files')
p.add_argument('-p', '--pathways_file',
               default=os.path.join(cfg.pathway_data, 'canonical_mapped.tsv'),
               help='pathways file to use for PLIER, see\
                     0B.preprocess_plier_data.ipynb for file format')
p.add_argument('-s', '--shuffle', action='store_true',
               help='randomize gene expression data for negative control')
p.add_argument('-v', '--verbose', action='store_true')
args = p.parse_args()

algs_to_run = ([args.algorithm] if args.algorithm
                                else DataModel.list_algorithms())

if args.verbose:
    logging.basicConfig(level=logging.DEBUG, format='%(message)s')

# load input expression data
rnaseq_train_df, rnaseq_test_df = du.load_expression_data(
        subset_mad_genes=args.subset_mad_genes, scale_input=False,
        verbose=args.verbose)

dm = DataModel(df=rnaseq_train_df, test_df=rnaseq_test_df)
# TODO: per-algorithm transformations (e.g. NMF doesn't work with negative
# values, PLIER doesn't work with zeros)
dm.transform(how='zscore')

if args.shuffle:
    file_prefix = '{}_components_shuffled_'.format(args.num_components)
else:
    file_prefix = '{}_components_'.format(args.num_components)

# specify location of output files

comp_out_dir = os.path.join(os.path.abspath(args.models_dir),
                            'ensemble_z_matrices',
                            'components_{}'.format(args.num_components))

if not os.path.exists(comp_out_dir):
    os.makedirs(comp_out_dir)

np.random.seed(cfg.default_seed)
random_seeds = np.random.choice(np.arange(0, 1000000), size=args.num_seeds)

reconstruction_results = []
test_reconstruction_results = []

logging.debug('Fitting compression models...')
recon_file = os.path.join(args.models_dir,
                          '{}reconstruction.tsv'.format(
                          file_prefix))

for ix, seed in enumerate(random_seeds, 1):
    np.random.seed(seed)
    seed_name = seed
    if args.shuffle:
        seed_name = '{}_shuffled'.format(seed_name)
        shuffled_train_df = shuffle_train_genes(rnaseq_train_df)
        dm = DataModel(df=shuffled_train_df,
                       test_df=rnaseq_test_df)
        dm.transform(how='zscore')

    if 'pca' in algs_to_run:
        logging.debug('-- Fitting pca model for random seed {} of {}'.format(
                      ix, len(random_seeds)))
        dm.pca(n_components=args.num_components,
               transform_test_df=True)
    if 'ica' in algs_to_run:
        logging.debug('-- Fitting ica model for random seed {} of {}'.format(
                      ix, len(random_seeds)))
        dm.ica(n_components=args.num_components,
               transform_test_df=True,
               seed=seed)
    if 'nmf' in algs_to_run:
        logging.debug('-- Fitting nmf model for random seed {} of {}'.format(
                      ix, len(random_seeds)))
        dm.nmf(n_components=args.num_components,
               transform_test_df=True,
               seed=seed)
    if 'plier' in algs_to_run:
        logging.debug('-- Fitting PLIER model for random seed {} of {}'.format(
                      ix, len(random_seeds)))
        dm.plier(n_components=args.num_components,
                 pathways_file=args.pathways_file,
                 transform_test_df=True,
                 shuffled=args.shuffle,
                 seed=seed,
                 verbose=args.verbose)


    # Obtain z matrix (sample scores per latent space feature) for all models
    z_suffix = '{}_z_matrix.tsv.gz'.format(seed_name)
    dm.write_models(comp_out_dir, z_suffix)

    test_z_suffix = '{}_z_test_matrix.tsv.gz'.format(seed_name)
    dm.write_models(comp_out_dir, test_z_suffix, test_set=True)

    # Obtain weight matrices (gene by latent space feature) for all models
    weight_suffix = '{}_weight_matrix.tsv.gz'.format(seed_name)
    dm.write_weight_matrices(comp_out_dir, weight_suffix)

    # Store reconstruction costs and reconstructed input at training end
    full_reconstruction, reconstructed_matrices = dm.compile_reconstruction()

    # Store reconstruction evaluation and data for test set
    full_test_recon, test_recon_mat = dm.compile_reconstruction(test_set=True)

    reconstruction_results.append(
        full_reconstruction.assign(seed=seed, shuffled=args.shuffle)
        )

    test_reconstruction_results.append(
        full_test_recon.assign(seed=seed, shuffled=args.shuffle)
        )

# Save reconstruction results
pd.concat([
    pd.concat(reconstruction_results).assign(data_type='training'),
    pd.concat(test_reconstruction_results).assign(data_type='testing')
]).reset_index(drop=True).to_csv(recon_file, sep='\t', index=False)

