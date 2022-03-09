#!/usr/bin/env python
# coding: utf-8

import wf_psf as wf

# ----------------------- #
# WaveDiff-original
args = {
    'model':  'poly',
    'id_name':  '_sample_w_bis1_2k',
    'base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/',
    'log_folder':  "log-files/",
    'model_folder':  "chkp/",
    'optim_hist_folder':  "optim-hist/",
    'plots_folder': "plots/" ,
    'dataset_folder':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/data/coherent_euclid_dataset/',
    'metric_base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/metrics/',
    'chkp_save_path':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/papers/article_IOP/data/models/wavediff-original/',
    'train_dataset_file':  'train_Euclid_res_2000_TrainStars_id_001.npy',
    'test_dataset_file':  'test_Euclid_res_id_001.npy',
    'n_zernikes':  15,
    'pupil_diameter':  256,
    'n_bins_lda':  20,
    'output_q':  3.,
    'oversampling_rate':  3.,
    'output_dim':  32,
    'd_max':  2,
    'd_max_nonparam':  5,
    'x_lims':  [0, 1e3],
    'y_lims':  [0, 1e3],
    'graph_features': 10,
    'l1_rate':  1e-8,
    'use_sample_weights':  True,
    'batch_size':  32,
    'l_rate_param':  [0.01,0.004],
    'l_rate_non_param':  [0.1,0.06],
    'n_epochs_param':  [15,15],
    'n_epochs_non_param':  [100,50],
    'total_cycles':  2,
    'saved_model_type':  'checkpoint',
    'saved_cycle':  'cycle2',
    'gt_n_zernikes':  45,
    'eval_batch_size':  16,
    'l2_param':  0.,
    'base_id_name':  '_sample_w_bis1_',
    'suffix_id_name':  '2k',
    'star_numbers':  2000,
}
wf.script_utils.evaluate_model(**args)
wf.script_utils.plot_metrics(**args)

# ----------------------- #
# WaveDiff-graph
args = {
    'model':  'graph',
    'id_name':  '_sample_w_tunned_2k',
    'base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/',
    'log_folder':  "log-files/",
    'model_folder':  "chkp/",
    'optim_hist_folder':  "optim-hist/",
    'plots_folder': "plots/" ,
    'dataset_folder':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/data/coherent_euclid_dataset/',
    'metric_base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/metrics/',
    'chkp_save_path':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/papers/article_IOP/data/models/wavediff-graph/',
    'train_dataset_file':  'train_Euclid_res_2000_TrainStars_id_001.npy',
    'test_dataset_file':  'test_Euclid_res_id_001.npy',
    'n_zernikes':  15,
    'pupil_diameter':  256,
    'n_bins_lda':  20,
    'output_q':  3.,
    'oversampling_rate':  3.,
    'output_dim':  32,
    'd_max':  2,
    'd_max_nonparam':  3,
    'x_lims':  [0, 1e3],
    'y_lims':  [0, 1e3],
    'graph_features': 21,
    'l1_rate':  1e-8,
    'use_sample_weights':  True,
    'batch_size':  32,
    'l_rate_param':  [0.01,0.004],
    'l_rate_non_param':  [0.4,0.2],
    'n_epochs_param':  [15,15],
    'n_epochs_non_param':  [100,50],
    'total_cycles':  2,
    'saved_model_type':  'checkpoint',
    'saved_cycle':  'cycle2',
    'gt_n_zernikes':  45,
    'eval_batch_size':  16,
    'l2_param':  0.,
    'base_id_name':  '_sample_w_tunned_',
    'suffix_id_name':  '2k',
    'star_numbers':  2000,
}
wf.script_utils.evaluate_model(**args)
wf.script_utils.plot_metrics(**args)

# ----------------------- #
# WaveDiff-polygraph
args = {
    'model':  'mccd',
    'id_name':  '_sample_w_bis2_2k',
    'base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/',
    'log_folder':  "log-files/",
    'model_folder':  "chkp/",
    'optim_hist_folder':  "optim-hist/",
    'plots_folder': "plots/" ,
    'dataset_folder':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/data/coherent_euclid_dataset/',
    'metric_base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/metrics/',
    'chkp_save_path':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/papers/article_IOP/data/models/wavediff-polygraph/',
    'train_dataset_file':  'train_Euclid_res_2000_TrainStars_id_001.npy',
    'test_dataset_file':  'test_Euclid_res_id_001.npy',
    'n_zernikes':  15,
    'pupil_diameter':  256,
    'n_bins_lda':  20,
    'output_q':  3.,
    'oversampling_rate':  3.,
    'output_dim':  32,
    'd_max':  2,
    'd_max_nonparam':  3,
    'x_lims':  [0, 1e3],
    'y_lims':  [0, 1e3],
    'graph_features': 10,
    'l1_rate':  1e-8,
    'use_sample_weights':  True,
    'batch_size':  32,
    'l_rate_param':  [0.01,0.004],
    'l_rate_non_param':  [0.1,0.06],
    'n_epochs_param':  [15,15],
    'n_epochs_non_param':  [100,50],
    'total_cycles':  2,
    'saved_model_type':  'checkpoint',
    'saved_cycle':  'cycle2',
    'gt_n_zernikes':  45,
    'eval_batch_size':  16,
    'l2_param':  0.,
    'base_id_name':  '_sample_w_bis2_',
    'suffix_id_name':  '2k',
    'star_numbers':  2000,
}
wf.script_utils.evaluate_model(**args)
wf.script_utils.plot_metrics(**args)

# ----------------------- #
# WaveDiff-zernike15
args = {
    'model':  'param',
    'id_name':  '_incomplete_15_sample_w_2k',
    'base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/',
    'log_folder':  "log-files/",
    'model_folder':  "chkp/",
    'optim_hist_folder':  "optim-hist/",
    'plots_folder': "plots/" ,
    'dataset_folder':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/data/coherent_euclid_dataset/',
    'metric_base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/metrics/',
    'chkp_save_path':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/papers/article_IOP/data/models/zernike_15/',
    'train_dataset_file':  'train_Euclid_res_2000_TrainStars_id_001.npy',
    'test_dataset_file':  'test_Euclid_res_id_001.npy',
    'n_zernikes':  15,
    'pupil_diameter':  256,
    'n_bins_lda':  20,
    'output_q':  3.,
    'oversampling_rate':  3.,
    'output_dim':  32,
    'd_max':  2,
    'd_max_nonparam':  3,
    'x_lims':  [0, 1e3],
    'y_lims':  [0, 1e3],
    'graph_features': 10,
    'l1_rate':  1e-8,
    'use_sample_weights':  True,
    'batch_size':  32,
    'l_rate_param':  [0.005,0.001],
    'l_rate_non_param':  [0.1,0.06],
    'n_epochs_param':  [20,20],
    'n_epochs_non_param':  [100,50],
    'total_cycles':  2,
    'saved_model_type':  'checkpoint',
    'saved_cycle':  'cycle2',
    'gt_n_zernikes':  45,
    'eval_batch_size':  16,
    'l2_param':  0.,
    'base_id_name':  '_incomplete_15_sample_w_',
    'suffix_id_name':  '2k',
    'star_numbers':  2000,
}
wf.script_utils.evaluate_model(**args)
wf.script_utils.plot_metrics(**args)

# ----------------------- #
# WaveDiff-zernike45
args = {
    'model':  'param',
    'id_name':  '_incomplete_40_sample_w_bis1_2k',
    'base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/',
    'log_folder':  "log-files/",
    'model_folder':  "chkp/",
    'optim_hist_folder':  "optim-hist/",
    'plots_folder': "plots/" ,
    'dataset_folder':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/data/coherent_euclid_dataset/',
    'metric_base_path':  '/gpfswork/rech/ynx/ulx23va/wf-outputs/rerun_paper_results/metrics/',
    'chkp_save_path':  '/gpfswork/rech/ynx/ulx23va/repo/wf-psf/papers/article_IOP/data/models/zernike_40/',
    'train_dataset_file':  'train_Euclid_res_2000_TrainStars_id_001.npy',
    'test_dataset_file':  'test_Euclid_res_id_001.npy',
    'n_zernikes':  40,
    'pupil_diameter':  256,
    'n_bins_lda':  20,
    'output_q':  3.,
    'oversampling_rate':  3.,
    'output_dim':  32,
    'd_max':  2,
    'd_max_nonparam':  3,
    'x_lims':  [0, 1e3],
    'y_lims':  [0, 1e3],
    'graph_features': 10,
    'l1_rate':  1e-8,
    'use_sample_weights':  True,
    'batch_size':  32,
    'l_rate_param':  [0.005,0.001],
    'l_rate_non_param':  [0.1,0.06],
    'n_epochs_param':  [20,20],
    'n_epochs_non_param':  [100,50],
    'total_cycles':  2,
    'saved_model_type':  'checkpoint',
    'saved_cycle':  'cycle2',
    'gt_n_zernikes':  45,
    'eval_batch_size':  16,
    'l2_param':  0.,
    'base_id_name':  '_incomplete_40_sample_w_bis1_',
    'suffix_id_name':  '2k',
    'star_numbers':  2000,
}
wf.script_utils.evaluate_model(**args)
wf.script_utils.plot_metrics(**args)

print('Done..')