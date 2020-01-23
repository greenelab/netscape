import numpy as np
import itertools as it
import networkx as nx

def save_numpy_to_el(adj, nodelist, filename):
    """Save the given adjacency matrix to file (in edgelist format)."""
    G = nx.from_numpy_matrix(adj)
    G = nx.relabel_nodes(G, {ix: n for ix, n in enumerate(nodelist)})
    nx.write_weighted_edgelist(G, filename, delimiter='\t')


def generate_and_save_network(is_correlated, filename):
    """Generate binary network and save to filename."""
    n = is_correlated.shape[0]
    mnet = np.zeros((n, n))
    nodelist = np.arange(n)

    for (i, j) in it.combinations(range(n), 2):
        if is_correlated[i] and is_correlated[j]:
            mnet[i, j] = 1.0
            mnet[j, i] = 1.0

    for k in range(n):
        if not is_correlated[k]:
            mnet[k, k] = 1.0

    save_numpy_to_el(mnet, nodelist, filename)


def simulate_network(n, p, uncorr_frac, num_networks, seed=1, verbose=False):
    """Simulate data from a log-linear model with network collinearity.

    In this case, "network collinearity" means that we split the p features
    into num_network groups, and draw a single coefficient for each group
    (thus, every feature in each group has the same regression coefficient).

    Then, a network is generated in which features in the same group are
    connected by an edge of weight 1, and features in different groups are
    not connected. Thus, the network should contribute extra information
    to the model, which should help it find a better fit.

    This is useful mostly as a positive control (that is, since the network
    conveys perfect information about the collinearity of the features,
    including it should give us a better predictive model).

    Parameters
    ----------
    n: int
        number of samples

    p: int
        number of features

    uncorr_frac: float
        Fraction of features to be uncorrelated with outcome (between 0 and 1)

    num_networks: int
        Number of networks to partition the features into

    seed: int
        Seed for random number generator

    verbose: bool
        Whether to print verbose output or not

    Returns
    -------
    X: array_like, (n, p)
        Simulated features/samples

    B: array_like, (p,)
        Simulated coefficients

    y: array_like, (n, 1)
        Simulated labels in {0, 1}

    is_correlated: array_like, (p, 1)
        Whether or not each feature is correlated with the label

    adj_matrix: array_like, (p, p)
        Network of regression coefficients in adjacency matrix form

    network_groups: array_like, (p,)
        Partition of array indices into networks, generated by np.array_split

    """
    np.random.seed(seed)

    p_uncorr = int(uncorr_frac * p)
    p_corr = p - p_uncorr

    is_correlated = np.zeros(p).astype('bool')
    is_correlated[:p_corr] = True

    if verbose:
        print('Number of informative features: {}'.format(p_corr))
        print('Number of uninformative features: {}'.format(p_uncorr))

    adj_matrix = np.eye(p)
    network_groups = np.array_split(np.arange(p_corr), num_networks)
    for group in network_groups:
        for (i, j) in it.combinations(group, 2):
            adj_matrix[i, j] = 1
            adj_matrix[j, i] = 1

    X = np.random.randn(n, p)
    B = np.zeros((p_corr,))
    for group in network_groups:
        B[group] = np.random.randn()
    B = np.concatenate((np.random.randn(1), B))

    # calculate Bernoulli parameter pi(x_i) for each sample x_i
    linsum = B[0] + (X[:, :p_corr] @ B[1:, np.newaxis])
    pis = 1 / (1 + np.exp(-linsum))

    y = np.random.binomial(1, pis.flatten())

    return (X, B, y, is_correlated, adj_matrix, network_groups)


def simulate_network_reg(n, p, uncorr_frac, num_networks, noise_stdev=0,
                         seed=1, verbose=False):
    """Simulate data from a linear model with network collinearity.

    See simulate_network docstring for details of how coefficients and the
    network are generated. In this case, the outputs y are real-valued rather
    than binary, but otherwise the data generation process is similar.

    The noise_stdev parameter controls the Gaussian noise added to the
    real-valued labels (defaults to 0; i.e. labels are an exact linear
    combination of the features, with weights given by B).
    """
    import itertools as it
    import networkx as nx

    np.random.seed(seed)

    p_uncorr = int(uncorr_frac * p)
    p_corr = p - p_uncorr

    is_correlated = np.zeros(p).astype('bool')
    is_correlated[:p_corr] = True

    if verbose:
        print('Number of informative features: {}'.format(p_corr))
        print('Number of uninformative features: {}'.format(p_uncorr))

    adj_matrix = np.eye(p)
    network_groups = np.array_split(np.arange(p_corr), num_networks)
    for group in network_groups:
        for (i, j) in it.combinations(group, 2):
            adj_matrix[i, j] = 1
            adj_matrix[j, i] = 1

    X = np.random.randn(n, p)
    B = np.zeros((p_corr,))
    for group in network_groups:
        B[group] = np.random.randn()
    B = np.concatenate((np.random.randn(1), B))

    # calculate y = B_0 + X @ B (+ noise if necessary)
    y = B[0] + (X[:, :p_corr] @ B[1:, np.newaxis])
    if noise_stdev > 0:
        y += np.random.normal(scale=noise_stdev, size=(n, 1))

    return (X, B, y, is_correlated, adj_matrix, network_groups)
