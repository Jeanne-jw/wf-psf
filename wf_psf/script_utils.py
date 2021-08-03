# Import packages
import sys
import numpy as np
import time
import tensorflow as tf
import tensorflow_addons as tfa

import wf_psf.SimPSFToolkit as SimPSFToolkit
import wf_psf.utils as wf_utils
import wf_psf.tf_mccd_psf_field as tf_mccd_psf_field
import wf_psf.tf_psf_field as tf_psf_field
import wf_psf.metrics as wf_metrics
import wf_psf.train_utils as wf_train_utils

try:
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    import matplotlib.ticker as mtick
    import seaborn as sns
except:
    print('\nProblem importing plotting packages: matplotlib and seaborn.\n')

def train_model(**args):
    r""" Train the PSF model.
    
    For parameters check the training script click help.

    """
    # Start measuring elapsed time
    starting_time = time.time()

    # Define model run id
    run_id_name = args['model'] + args['id_name']

    # Define paths
    log_save_file = args['base_path'] + args['log_folder']
    model_save_file= args['base_path'] + args['model_folder']
    optim_hist_file = args['base_path']  + args['optim_hist_folder']
    saving_optim_hist = dict()


    # Save output prints to logfile
    old_stdout = sys.stdout
    log_file = open(log_save_file + run_id_name + '_output.log','w')
    sys.stdout = log_file
    print('Starting the log file.')

    # Print GPU and tensorflow info
    device_name = tf.test.gpu_device_name()
    print('Found GPU at: {}'.format(device_name))
    print('tf_version: ' + str(tf.__version__))

    ## Prepare the inputs
    # Generate Zernike maps
    zernikes = wf_utils.zernike_generator(n_zernikes=args['n_zernikes'], wfe_dim=args['pupil_diameter'])
    # Now as cubes
    np_zernike_cube = np.zeros((len(zernikes), zernikes[0].shape[0], zernikes[0].shape[1]))
    for it in range(len(zernikes)):
        np_zernike_cube[it,:,:] = zernikes[it]
    np_zernike_cube[np.isnan(np_zernike_cube)] = 0
    tf_zernike_cube = tf.convert_to_tensor(np_zernike_cube, dtype=tf.float32)
    print('Zernike cube:')
    print(tf_zernike_cube.shape)


    ## Load the dictionaries
    train_dataset = np.load(args['dataset_folder'] + args['train_dataset_file'], allow_pickle=True)[()]
    # train_stars = train_dataset['stars']
    # noisy_train_stars = train_dataset['noisy_stars']
    # train_pos = train_dataset['positions']
    train_SEDs = train_dataset['SEDs']
    # train_zernike_coef = train_dataset['zernike_coef']
    # train_C_poly = train_dataset['C_poly']
    train_parameters = train_dataset['parameters']

    test_dataset = np.load(args['dataset_folder'] + args['test_dataset_file'], allow_pickle=True)[()]
    # test_stars = test_dataset['stars']
    # test_pos = test_dataset['positions']
    test_SEDs = test_dataset['SEDs']
    # test_zernike_coef = test_dataset['zernike_coef']

    # Convert to tensor
    tf_noisy_train_stars = tf.convert_to_tensor(train_dataset['noisy_stars'], dtype=tf.float32)
    # tf_train_stars = tf.convert_to_tensor(train_dataset['stars'], dtype=tf.float32)
    tf_train_pos = tf.convert_to_tensor(train_dataset['positions'], dtype=tf.float32)
    tf_test_stars = tf.convert_to_tensor(test_dataset['stars'], dtype=tf.float32)
    tf_test_pos = tf.convert_to_tensor(test_dataset['positions'], dtype=tf.float32)

    print('Dataset parameters:')
    print(train_parameters)


    ## Generate initializations
    # Prepare np input
    simPSF_np = SimPSFToolkit(
        zernikes,
        max_order=args['n_zernikes'],
        pupil_diameter=args['pupil_diameter'],
        output_dim=args['output_dim'],
        oversampling_rate=args['oversampling_rate'],
        output_Q=args['output_q']
    )
    simPSF_np.gen_random_Z_coeffs(max_order=args['n_zernikes'])
    z_coeffs = simPSF_np.normalize_zernikes(simPSF_np.get_z_coeffs(), simPSF_np.max_wfe_rms)
    simPSF_np.set_z_coeffs(z_coeffs)
    simPSF_np.generate_mono_PSF(lambda_obs=0.7, regen_sample=False)
    # Obscurations
    obscurations = simPSF_np.generate_pupil_obscurations(N_pix=args['pupil_diameter'], N_filter=2)
    tf_obscurations = tf.convert_to_tensor(obscurations, dtype=tf.complex64)
    # Initialize the SED data list
    packed_SED_data = [
        wf_utils.generate_packed_elems(
            _sed,
            simPSF_np,
            n_bins=args['n_bins_lda']
        )
        for _sed in train_SEDs
    ]


    # Prepare the inputs for the training
    tf_packed_SED_data = tf.convert_to_tensor(packed_SED_data, dtype=tf.float32)
    tf_packed_SED_data = tf.transpose(tf_packed_SED_data, perm=[0, 2, 1])

    inputs = [tf_train_pos, tf_packed_SED_data]

    # Select the observed stars (noisy or noiseless)
    outputs = tf_noisy_train_stars
    # outputs = tf_train_stars


    ## Prepare validation data inputs
    val_SEDs = test_SEDs
    tf_val_pos = tf_test_pos
    tf_val_stars = tf_test_stars

    # Initialize the SED data list
    val_packed_SED_data = [
        wf_utils.generate_packed_elems(
            _sed,
            simPSF_np,
            n_bins=args['n_bins_lda']
        )
        for _sed in val_SEDs
    ]

    # Prepare the inputs for the validation
    tf_val_packed_SED_data = tf.convert_to_tensor(val_packed_SED_data, dtype=tf.float32)
    tf_val_packed_SED_data = tf.transpose(tf_val_packed_SED_data, perm=[0, 2, 1])
                    
    # Prepare input validation tuple
    val_x_inputs = [tf_val_pos, tf_val_packed_SED_data]
    val_y_inputs = tf_val_stars
    val_data = (val_x_inputs, val_y_inputs)


    ## Select the model
    if args['model'] == 'mccd':
        poly_dic, graph_dic = tf_mccd_psf_field.build_mccd_spatial_dic_v2(
            obs_stars=outputs.numpy(),
            obs_pos=tf_train_pos.numpy(),
            x_lims=args['x_lims'],
            y_lims=args['y_lims'],
            d_max=args['d_max_nonparam'],
            graph_features=args['graph_features']
        )

        spatial_dic = [poly_dic, graph_dic]

        # Initialize the model
        tf_semiparam_field = tf_mccd_psf_field.TF_SP_MCCD_field(
            zernike_maps=tf_zernike_cube,
            obscurations=tf_obscurations,
            batch_size=args['batch_size'],
            obs_pos=tf_train_pos,
            spatial_dic=spatial_dic,
            output_Q=args['output_q'],
            d_max_nonparam=args['d_max_nonparam'],
            graph_features=args['graph_features'],
            l1_rate=args['l1_rate'],
            output_dim=args['output_dim'],
            n_zernikes=args['n_zernikes'],
            d_max=args['d_max'],
            x_lims=args['x_lims'],
            y_lims=args['y_lims']
        )

    elif args['model'] == 'poly':
        # # Initialize the model
        tf_semiparam_field = tf_psf_field.TF_SemiParam_field(
            zernike_maps=tf_zernike_cube,
            obscurations=tf_obscurations,
            batch_size=args['batch_size'],
            output_Q=args['output_q'],
            d_max_nonparam=args['d_max_nonparam'],
            l2_param=args['l2_param'],
            output_dim=args['output_dim'],
            n_zernikes=args['n_zernikes'],
            d_max=args['d_max'],
            x_lims=args['x_lims'],
            y_lims=args['y_lims']
        )

    elif args['model'] == 'param':
        # Initialize the model
        tf_semiparam_field = tf_psf_field.TF_PSF_field_model(
            zernike_maps=tf_zernike_cube,
            obscurations=tf_obscurations,
            batch_size=args['batch_size'],
            output_Q=args['output_q'],
            l2_param=args['l2_param'],
            output_dim=args['output_dim'],
            n_zernikes=args['n_zernikes'],
            d_max=args['d_max'],
            x_lims=args['x_lims'],
            y_lims=args['y_lims']
        )


    # # Model Training
    # Prepare the saving callback
    # Prepare to save the model as a callback
    filepath_chkp_callback = args['chkp_save_path'] + 'chkp_callback_' + run_id_name + '_cycle1'
    model_chkp_callback = tf.keras.callbacks.ModelCheckpoint(
        filepath_chkp_callback,
        monitor='mean_squared_error',
        verbose=1,
        save_best_only=True,
        save_weights_only=False,
        mode='min',
        save_freq='epoch',
        options=None
    )

    # Prepare the optimisers
    param_optim = tfa.optimizers.RectifiedAdam(lr=args['l_rate_param'][0])
    non_param_optim = tfa.optimizers.RectifiedAdam(lr=args['l_rate_non_param'][0])

    print('Starting cycle 1..')
    start_cycle1 = time.time()

    if args['model'] == 'param':
        tf_semiparam_field, hist_param = wf_train_utils.param_train_cycle(
            tf_semiparam_field,
            inputs=inputs,
            outputs=outputs,
            val_data=val_data,
            batch_size=args['batch_size'],
            l_rate=args['l_rate_param'][0],
            n_epochs=args['n_epochs_param'][0], 
            param_optim=param_optim,
            param_loss=None, 
            param_metrics=None, 
            param_callback=None, 
            general_callback=[model_chkp_callback],
            use_sample_weights=args['use_sample_weights'],
            verbose=2
        )

    else:
        tf_semiparam_field, hist_param, hist_non_param = wf_train_utils.general_train_cycle(
            tf_semiparam_field,
            inputs=inputs,
            outputs=outputs,
            val_data=val_data,
            batch_size=args['batch_size'],
            l_rate_param=args['l_rate_param'][0],
            l_rate_non_param=args['l_rate_non_param'][0],
            n_epochs_param=args['n_epochs_param'][0],
            n_epochs_non_param=args['n_epochs_non_param'][0],
            param_optim=param_optim,
            non_param_optim=non_param_optim,
            param_loss=None,
            non_param_loss=None,
            param_metrics=None,
            non_param_metrics=None,
            param_callback=None,
            non_param_callback=None,
            general_callback=[model_chkp_callback],
            first_run=True,
            use_sample_weights=args['use_sample_weights'],
            verbose=2
        )

    # Save weights
    tf_semiparam_field.save_weights(model_save_file + 'chkp_' + run_id_name + '_cycle1')

    end_cycle1 = time.time()
    print('Cycle1 elapsed time: %f'%(end_cycle1-start_cycle1))

    # Save optimisation history in the saving dict
    saving_optim_hist['param_cycle1'] = hist_param.history
    if args['model'] != 'param':
        saving_optim_hist['nonparam_cycle1'] = hist_non_param.history

    if args['total_cycles'] >= 2:
        # Prepare to save the model as a callback
        filepath_chkp_callback = args['chkp_save_path'] + 'chkp_callback_' + run_id_name + '_cycle2'
        model_chkp_callback = tf.keras.callbacks.ModelCheckpoint(
            filepath_chkp_callback,
            monitor='mean_squared_error',
            verbose=1,
            save_best_only=True,
            save_weights_only=False,
            mode='min',
            save_freq='epoch',
            options=None
        )

        # Prepare the optimisers
        param_optim = tfa.optimizers.RectifiedAdam(lr=args['l_rate_param'][1])
        non_param_optim = tfa.optimizers.RectifiedAdam(lr=args['l_rate_non_param'][1])

        print('Starting cycle 2..')
        start_cycle2 = time.time()


        # Compute the next cycle
        if args['model'] == 'param':
            tf_semiparam_field, hist_param_2 = wf_train_utils.param_train_cycle(
                tf_semiparam_field,
                inputs=inputs,
                outputs=outputs,
                val_data=val_data,
                batch_size=args['batch_size'],
                l_rate=args['l_rate_param'][1],
                n_epochs=args['n_epochs_param'][1], 
                param_optim=param_optim,
                param_loss=None, 
                param_metrics=None, 
                param_callback=None, 
                general_callback=[model_chkp_callback],
                use_sample_weights=args['use_sample_weights'],
                verbose=2
            )
        else:
            # Compute the next cycle
            tf_semiparam_field, hist_param_2, hist_non_param_2 = wf_train_utils.general_train_cycle(
                tf_semiparam_field,
                inputs=inputs,
                outputs=outputs,
                val_data=val_data,
                batch_size=args['batch_size'],
                l_rate_param=args['l_rate_param'][1],
                l_rate_non_param=args['l_rate_non_param'][1],
                n_epochs_param=args['n_epochs_param'][1],
                n_epochs_non_param=args['n_epochs_non_param'][1],
                param_optim=param_optim,
                non_param_optim=non_param_optim,
                param_loss=None,
                non_param_loss=None,
                param_metrics=None,
                non_param_metrics=None,
                param_callback=None,
                non_param_callback=None,
                general_callback=[model_chkp_callback],
                first_run=False,
                use_sample_weights=args['use_sample_weights'],
                verbose=2
            )

        # Save the weights at the end of the second cycle
        tf_semiparam_field.save_weights(model_save_file + 'chkp_' + run_id_name + '_cycle2')

        end_cycle2 = time.time()
        print('Cycle2 elapsed time: %f'%(end_cycle2 - start_cycle2))

        # Save optimisation history in the saving dict
        saving_optim_hist['param_cycle2'] = hist_param_2.history
        if args['model'] != 'param':
            saving_optim_hist['nonparam_cycle2'] = hist_non_param_2.history

    # Save optimisation history dictionary
    np.save(optim_hist_file + 'optim_hist_' + run_id_name + '.npy', saving_optim_hist)

    ## Print final time
    final_time = time.time()
    print('\nTotal elapsed time: %f'%(final_time - starting_time))

    ## Close log file
    print('\n Good bye..')
    sys.stdout = old_stdout
    log_file.close()


def evaluate_model(**args):
    r""" Evaluate the trained model.
    
    For parameters check the training script click help.

    """
    # Start measuring elapsed time
    starting_time = time.time()

    # Define model run id
    run_id_name = args['model'] + args['id_name']
    # Define paths
    log_save_file = args['base_path'] + args['log_folder']

    # Define saved model to use
    if args['saved_model_type'] == 'checkpoint':
        weights_paths = args['chkp_save_path'] + 'chkp_callback_' + run_id_name + '_' + args['saved_cycle']

    elif args['saved_model_type'] == 'final':
        model_save_file= args['base_path'] + args['model_folder']
        weights_paths = model_save_file + 'chkp_' + run_id_name + '_' + args['saved_cycle']

    
    ## Save output prints to logfile
    old_stdout = sys.stdout
    log_file = open(log_save_file + run_id_name + '-metrics_output.log', 'w')
    sys.stdout = log_file
    print('Starting the log file.')

    ## Check GPU and tensorflow version
    device_name = tf.test.gpu_device_name()
    print('Found GPU at: {}'.format(device_name))
    print('tf_version: ' + str(tf.__version__))


    ## Load datasets
    train_dataset = np.load(args['dataset_folder'] + args['train_dataset_file'], allow_pickle=True)[()]
    # train_stars = train_dataset['stars']
    # noisy_train_stars = train_dataset['noisy_stars']
    # train_pos = train_dataset['positions']
    train_SEDs = train_dataset['SEDs']
    # train_zernike_coef = train_dataset['zernike_coef']
    train_C_poly = train_dataset['C_poly']
    train_parameters = train_dataset['parameters']

    test_dataset = np.load(args['dataset_folder'] + args['test_dataset_file'], allow_pickle=True)[()]
    # test_stars = test_dataset['stars']
    # test_pos = test_dataset['positions']
    test_SEDs = test_dataset['SEDs']
    # test_zernike_coef = test_dataset['zernike_coef']

    # Convert to tensor
    tf_noisy_train_stars = tf.convert_to_tensor(train_dataset['noisy_stars'], dtype=tf.float32)
    tf_train_pos = tf.convert_to_tensor(train_dataset['positions'], dtype=tf.float32)
    tf_test_pos = tf.convert_to_tensor(test_dataset['positions'], dtype=tf.float32)

    print('Dataset parameters:')
    print(train_parameters)


    ## Prepare models
    # Generate Zernike maps
    zernikes = wf_utils.zernike_generator(n_zernikes=args['n_zernikes'], wfe_dim=args['pupil_diameter'])
    # Now as cubes
    np_zernike_cube = np.zeros((len(zernikes), zernikes[0].shape[0], zernikes[0].shape[1]))

    for it in range(len(zernikes)):
        np_zernike_cube[it,:,:] = zernikes[it]

    np_zernike_cube[np.isnan(np_zernike_cube)] = 0
    tf_zernike_cube = tf.convert_to_tensor(np_zernike_cube, dtype=tf.float32)

    # Prepare np input
    simPSF_np = SimPSFToolkit(
        zernikes,
        max_order=args['n_zernikes'],
        pupil_diameter=args['pupil_diameter'],
        output_dim=args['output_dim'],
        oversampling_rate=args['oversampling_rate'],
        output_Q=args['output_q']
    )
    simPSF_np.gen_random_Z_coeffs(max_order=args['n_zernikes'])
    z_coeffs = simPSF_np.normalize_zernikes(simPSF_np.get_z_coeffs(), simPSF_np.max_wfe_rms)
    simPSF_np.set_z_coeffs(z_coeffs)
    simPSF_np.generate_mono_PSF(lambda_obs=0.7, regen_sample=False)

    # Obscurations
    obscurations = simPSF_np.generate_pupil_obscurations(N_pix=args['pupil_diameter'], N_filter=2)
    tf_obscurations = tf.convert_to_tensor(obscurations, dtype=tf.complex64)

    # Outputs (needed for the MCCD model)
    outputs = tf_noisy_train_stars


    ## Create the model
    ## Select the model
    if args['model'] == 'mccd':
        poly_dic, graph_dic = tf_mccd_psf_field.build_mccd_spatial_dic_v2(
            obs_stars=outputs.numpy(),
            obs_pos=tf_train_pos.numpy(),
            x_lims=args['x_lims'],
            y_lims=args['y_lims'],
            d_max=args['d_max_nonparam'],
            graph_features=args['graph_features']
        )

        spatial_dic = [poly_dic, graph_dic]

       # Initialize the model
        tf_semiparam_field = tf_mccd_psf_field.TF_SP_MCCD_field(
            zernike_maps=tf_zernike_cube,
            obscurations=tf_obscurations,
            batch_size=args['batch_size'],
            obs_pos=tf_train_pos,
            spatial_dic=spatial_dic,
            output_Q=args['output_q'],
            d_max_nonparam=args['d_max_nonparam'],
            graph_features=args['graph_features'],
            l1_rate=args['l1_rate'],
            output_dim=args['output_dim'],
            n_zernikes=args['n_zernikes'],
            d_max=args['d_max'],
            x_lims=args['x_lims'],
            y_lims=args['y_lims']
        )

    elif args['model'] == 'poly':
        # # Initialize the model
        tf_semiparam_field = tf_psf_field.TF_SemiParam_field(
            zernike_maps=tf_zernike_cube,
            obscurations=tf_obscurations,
            batch_size=args['batch_size'],
            output_Q=args['output_q'],
            d_max_nonparam=args['d_max_nonparam'],
            l2_param=args['l2_param'],
            output_dim=args['output_dim'],
            n_zernikes=args['n_zernikes'],
            d_max=args['d_max'],
            x_lims=args['x_lims'],
            y_lims=args['y_lims']
        )

    elif args['model'] == 'param':
        # Initialize the model
        tf_semiparam_field = tf_psf_field.TF_PSF_field_model(
            zernike_maps=tf_zernike_cube,
            obscurations=tf_obscurations,
            batch_size=args['batch_size'],
            output_Q=args['output_q'],
            l2_param=args['l2_param'],
            output_dim=args['output_dim'],
            n_zernikes=args['n_zernikes'],
            d_max=args['d_max'],
            x_lims=args['x_lims'],
            y_lims=args['y_lims']
        )

    ## Load the model's weights
    tf_semiparam_field.load_weights(weights_paths)

    ## Prepare ground truth model
    # Generate Zernike maps
    zernikes = wf_utils.zernike_generator(n_zernikes=args['gt_n_zernikes'], wfe_dim=args['pupil_diameter'])
    # Now as cubes
    np_zernike_cube = np.zeros((len(zernikes), zernikes[0].shape[0], zernikes[0].shape[1]))
    for it in range(len(zernikes)):
        np_zernike_cube[it,:,:] = zernikes[it]

    np_zernike_cube[np.isnan(np_zernike_cube)] = 0
    tf_zernike_cube = tf.convert_to_tensor(np_zernike_cube, dtype=tf.float32)

    # Initialize the model
    GT_tf_semiparam_field = tf_psf_field.TF_SemiParam_field(
        zernike_maps=tf_zernike_cube,
        obscurations=tf_obscurations,
        batch_size=args['batch_size'],
        output_Q=args['output_q'],
        d_max_nonparam=args['d_max_nonparam'],
        output_dim=args['output_dim'],
        n_zernikes=args['gt_n_zernikes'],
        d_max=args['d_max'],
        x_lims=args['x_lims'],
        y_lims=args['y_lims']
    )

    # For the Ground truth model
    GT_tf_semiparam_field.tf_poly_Z_field.assign_coeff_matrix(train_C_poly)
    _ = GT_tf_semiparam_field.tf_np_poly_opd.alpha_mat.assign(
        np.zeros_like(GT_tf_semiparam_field.tf_np_poly_opd.alpha_mat)
    )


    ## Metric evaluation on the test dataset
    print('\n***\nMetric evaluation on the test dataset\n***\n')

    # Polychromatic star reconstructions
    rmse, rel_rmse, std_rmse, std_rel_rmse = wf_metrics.compute_poly_metric(
        tf_semiparam_field=tf_semiparam_field,
        GT_tf_semiparam_field=GT_tf_semiparam_field,
        simPSF_np=simPSF_np,
        tf_pos=tf_test_pos,
        tf_SEDs=test_SEDs,
        n_bins_lda=args['n_bins_lda'],
        batch_size=args['eval_batch_size']
    )

    poly_metric = {
        'rmse': rmse,
        'rel_rmse': rel_rmse,
        'std_rmse': std_rmse,
        'std_rel_rmse': std_rel_rmse
    }

    # Monochromatic star reconstructions
    lambda_list = np.arange(0.55, 0.9, 0.01)  # 10nm separation
    rmse_lda, rel_rmse_lda, std_rmse_lda, std_rel_rmse_lda = wf_metrics.compute_mono_metric(
        tf_semiparam_field=tf_semiparam_field,
        GT_tf_semiparam_field=GT_tf_semiparam_field,
        simPSF_np=simPSF_np,
        tf_pos=tf_test_pos,
        lambda_list=lambda_list
    )

    mono_metric = {
        'rmse_lda': rmse_lda,
        'rel_rmse_lda': rel_rmse_lda,
        'std_rmse_lda': std_rmse_lda,
        'std_rel_rmse_lda': std_rel_rmse_lda
    }

    # OPD metrics
    rmse_opd, rel_rmse_opd, rmse_std_opd, rel_rmse_std_opd = wf_metrics.compute_opd_metrics(
        tf_semiparam_field=tf_semiparam_field,
        GT_tf_semiparam_field=GT_tf_semiparam_field,
        pos=tf_test_pos,
        batch_size=args['eval_batch_size']
    )

    opd_metric = {
        'rmse_opd': rmse_opd,
        'rel_rmse_opd': rel_rmse_opd,
        'rmse_std_opd': rmse_std_opd,
        'rel_rmse_std_opd': rel_rmse_std_opd
    }

    # Shape metrics
    shape_results_dict = wf_metrics.compute_shape_metrics(
        tf_semiparam_field=tf_semiparam_field,
        GT_tf_semiparam_field=GT_tf_semiparam_field,
        simPSF_np=simPSF_np,
        SEDs=test_SEDs,
        tf_pos=tf_test_pos,
        n_bins_lda=args['n_bins_lda'],
        output_Q=1,
        output_dim=64,
        batch_size=args['eval_batch_size']
    )

    # Save metrics
    test_metrics = {
        'poly_metric': poly_metric,
        'mono_metric': mono_metric,
        'opd_metric': opd_metric,
        'shape_results_dict': shape_results_dict
    }


    ## Metric evaluation on the train dataset
    print('\n***\nMetric evaluation on the train dataset\n***\n')

    # Polychromatic star reconstructions
    rmse, rel_rmse, std_rmse, std_rel_rmse = wf_metrics.compute_poly_metric(
        tf_semiparam_field=tf_semiparam_field,
        GT_tf_semiparam_field=GT_tf_semiparam_field,
        simPSF_np=simPSF_np,
        tf_pos=tf_train_pos,
        tf_SEDs=train_SEDs,
        n_bins_lda=args['n_bins_lda'],
        batch_size=args['eval_batch_size']
    )

    train_poly_metric = {
        'rmse': rmse,
        'rel_rmse': rel_rmse,
        'std_rmse': std_rmse,
        'std_rel_rmse': std_rel_rmse
    }

    # Monochromatic star reconstructions
    lambda_list = np.arange(0.55, 0.9, 0.01)    # 10nm separation
    rmse_lda, rel_rmse_lda, std_rmse_lda, std_rel_rmse_lda = wf_metrics.compute_mono_metric(
        tf_semiparam_field=tf_semiparam_field,
        GT_tf_semiparam_field=GT_tf_semiparam_field,
        simPSF_np=simPSF_np,
        tf_pos=tf_train_pos,
        lambda_list=lambda_list
    )

    train_mono_metric = {
        'rmse_lda': rmse_lda,
        'rel_rmse_lda': rel_rmse_lda,
        'std_rmse_lda': std_rmse_lda,
        'std_rel_rmse_lda': std_rel_rmse_lda
    }

    # OPD metrics
    rmse_opd, rel_rmse_opd, rmse_std_opd, rel_rmse_std_opd = wf_metrics.compute_opd_metrics(
        tf_semiparam_field=tf_semiparam_field,
        GT_tf_semiparam_field=GT_tf_semiparam_field,
        pos=tf_train_pos,
        batch_size=args['eval_batch_size']
    )

    train_opd_metric = {
        'rmse_opd': rmse_opd,
        'rel_rmse_opd': rel_rmse_opd,
        'rmse_std_opd': rmse_std_opd,
        'rel_rmse_std_opd': rel_rmse_std_opd
    }

    # Shape metrics
    train_shape_results_dict = wf_metrics.compute_shape_metrics(
        tf_semiparam_field=tf_semiparam_field,
        GT_tf_semiparam_field=GT_tf_semiparam_field,
        simPSF_np=simPSF_np,
        SEDs=train_SEDs,
        tf_pos=tf_train_pos,
        n_bins_lda=args['n_bins_lda'],
        output_Q=1,
        output_dim=64,
        batch_size=args['eval_batch_size']
    )

    # Save metrics into dictionary
    train_metrics = {
        'poly_metric': train_poly_metric,
        'mono_metric': train_mono_metric,
        'opd_metric': train_opd_metric,
        'shape_results_dict': train_shape_results_dict
    }


    ## Save results
    metrics = {
        'test_metrics': test_metrics,
        'train_metrics': train_metrics
    }
    output_path = args['metric_base_path'] + 'metrics-' + run_id_name
    np.save(output_path, metrics, allow_pickle=True)

    ## Print final time
    final_time = time.time()
    print('\nTotal elapsed time: %f'%(final_time - starting_time))


    ## Close log file
    print('\n Good bye..')
    sys.stdout = old_stdout
    log_file.close()


def plot_metrics(**args):
    r""" Plot model results.
    """
    define_plot_style()

    plot_saving_path = args['base_path'] + args['plots_folder']

    # Define common data
    # Common data
    lambda_list = np.arange(0.55, 0.9, 0.01)
    star_list = np.array(args['star_numbers'])
    e1_req_euclid = 2e-04
    e2_req_euclid = 2e-04
    R2_req_euclid = 1e-03

    # Define the number of datasets to test
    n_datasets = len(args['suffix_id_name'])

    # Run id without suffix
    run_id_no_suff = args['model'] + args['base_id_name']

    # Define the metric data paths
    model_paths = [
        args['metric_base_path'] + 'metrics-' + run_id_no_suff + _suff + '.npy'  
        for _suff in args['suffix_id_name']
    ]
    # Load metrics
    metrics = [
        np.load(_path, allow_pickle=True)[()]
        for _path in model_paths
    ]

    for plot_dataset in ['test', 'train']:

        ## Polychromatic results
        res = extract_poly_results(metrics, test_train=plot_dataset)
        model_polyc_rmse = res[0]
        model_polyc_std_rmse = res[1]
        model_polyc_rel_rmse = res[2]
        model_polyc_std_rel_rmse = res[3]

        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        ax1.errorbar(
            x = star_list,
            y = model_polyc_rmse,
            yerr = model_polyc_std_rmse,
            label=run_id_no_suff,
            alpha=0.75
        )
        plt.minorticks_on()
        ax1.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        ax1.legend()
        ax1.set_title(
            'Stars ' + plot_dataset + '\n' + run_id_no_suff + '.\nPolychromatic pixel RMSE @ Euclid resolution'
        )
        ax1.set_xlabel('Number of stars')
        ax1.set_ylabel('Absolute error')
        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=4, marker='^', alpha=0.5)
        ax2.plot(star_list, model_polyc_rel_rmse, **kwargs)
        ax2.set_ylabel('Relative error [%]')  
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + plot_dataset + '-metrics-' + run_id_no_suff + '_polyc_pixel_RMSE.png'
        )
        plt.show()


        ## Monochromatic 
        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        for it in range(n_datasets):
            ax1.errorbar(
                x = lambda_list,
                y = metrics[it]['test_metrics']['mono_metric']['rmse_lda'],
                yerr = metrics[it]['test_metrics']['mono_metric']['std_rmse_lda'],
                label=args['model'] + args['suffix_id_name'][it],
                alpha=0.75
            )
        plt.minorticks_on()
        ax1.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        ax1.legend()
        ax1.set_title(
            'Stars ' + plot_dataset + '\n' + run_id_no_suff + '.\nMonochromatic pixel RMSE @ Euclid resolution'
        )
        ax1.set_xlabel('Wavelength [um]')
        ax1.set_ylabel('Absolute error')

        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=8, marker='^', alpha=0.5)
        for it in range(n_datasets):
            ax2.plot(
                lambda_list,
                metrics[it]['test_metrics']['mono_metric']['rel_rmse_lda'],
                **kwargs
            )
        ax2.set_ylabel('Relative error [%]')  
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + plot_dataset + '-metrics-' + run_id_no_suff + '_monochrom_pixel_RMSE.png'
        )
        plt.show()


        ## OPD results
        res = extract_opd_results(metrics, test_train=plot_dataset)
        model_opd_rmse = res[0]
        model_opd_std_rmse = res[1]
        model_opd_rel_rmse = res[2]
        model_opd_std_rel_rmse = res[3]

        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        ax1.errorbar(
            x=star_list,
            y=model_opd_rmse,
            yerr=model_opd_std_rmse,
            label=run_id_no_suff,
            alpha=0.75
        )
        plt.minorticks_on()
        ax1.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        ax1.legend()
        ax1.set_title(
            'Stars ' + plot_dataset + '\n' + run_id_no_suff + '.\nOPD RMSE'
            )
        ax1.set_xlabel('Number of stars')
        ax1.set_ylabel('Absolute error')

        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=8, marker='^', alpha=0.5)
        ax2.plot(star_list, model_opd_rel_rmse, **kwargs)
        ax2.set_ylabel('Relative error [%]')  
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + plot_dataset + '-metrics-' + run_id_no_suff + '_OPD_RMSE.png'
        )
        plt.show()

        ## Shape results
        model_e1, model_e2, model_R2 = extract_shape_results(metrics, test_train=plot_dataset)
        model_e1_rmse =             model_e1[0]
        model_e1_std_rmse =         model_e1[1]
        model_e1_rel_rmse =         model_e1[2]
        model_e1_std_rel_rmse =     model_e1[3]
        model_e2_rmse =             model_e2[0]
        model_e2_std_rmse =         model_e2[1]
        model_e2_rel_rmse =         model_e2[2]
        model_e2_std_rel_rmse =     model_e2[3]
        model_rmse_R2_meanR2 =      model_R2[0]
        model_std_rmse_R2_meanR2 =  model_R2[1]

        # Compute Euclid relative error values
        model_e1_rel_euclid = model_e1_rmse / e1_req_euclid
        model_e2_rel_euclid = model_e2_rmse / e2_req_euclid
        model_R2_rel_euclid = model_rmse_R2_meanR2 / R2_req_euclid

        # Plot e1 and e2
        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        ax1.errorbar(
            x=star_list,
            y=model_e1_rmse,
            yerr=model_e1_std_rmse,
            label='e1 ' + run_id_no_suff,
            alpha=0.75
        )
        ax1.errorbar(
            x=star_list,
            y=model_e2_rmse,
            yerr=model_e2_std_rmse,
            label='e2 ' + run_id_no_suff,
            alpha=0.75
        )
        plt.minorticks_on()
        ax1.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        ax1.legend()
        ax1.set_title(
            'Stars ' + plot_dataset + '\n' + run_id_no_suff + '\ne1, e2 RMSE @ 3x Euclid resolution'
        )
        ax1.set_xlabel('Number of stars')
        ax1.set_ylabel('Absolute error')

        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=8, marker='^', alpha=0.5)
        ax2.plot(star_list, model_e1_rel_euclid, **kwargs)
        ax2.plot(star_list, model_e2_rel_euclid, **kwargs)
        ax2.set_ylabel('Times over Euclid req.')  
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + plot_dataset + '-metrics-' + run_id_no_suff + '_shape_e1_e2_RMSE.png'
        )
        plt.show()

        # Plot R2
        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        ax1.errorbar(
            x=star_list,
            y=model_rmse_R2_meanR2,
            yerr=model_std_rmse_R2_meanR2,
            label='R2 ' + run_id_no_suff,
            alpha=0.75
        )
        plt.minorticks_on()
        ax1.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        ax1.legend()
        ax1.set_title(
            'Stars ' + plot_dataset + '\n' + run_id_no_suff + '\nR2/<R2> RMSE @ 3x Euclid resolution'
        )
        ax1.set_xlabel('Number of stars')
        ax1.set_ylabel('Absolute error')

        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=8, marker='^', alpha=0.5)
        ax2.plot(star_list, model_R2_rel_euclid, **kwargs)
        ax2.set_ylabel('Times over Euclid req.')  
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + plot_dataset + '-metrics-' + run_id_no_suff + '_shape_R2_RMSE.png'
        )
        plt.show()


        ## Polychromatic pixel residual at shape measurement resolution
        res = extract_shape_pix_results(metrics, test_train=plot_dataset)
        model_polyc_shpix_rmse = res[0]
        model_polyc_shpix_std_rmse = res[1]
        model_polyc_shpix_rel_rmse = res[2]
        model_polyc_shpix_std_rel_rmse = res[3]

        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        ax1.errorbar(
            x=star_list,
            y=model_polyc_shpix_rmse,
            yerr=model_polyc_shpix_std_rmse,
            label=run_id_no_suff,
            alpha=0.75
        )
        plt.minorticks_on()
        ax1.yaxis.set_major_formatter(mtick.FormatStrFormatter('%.1e'))
        ax1.legend()
        ax1.set_title(
            'Stars ' + plot_dataset + '\n' + run_id_no_suff + '\nPixel RMSE @ 3x Euclid resolution'
        )
        ax1.set_xlabel('Number of stars')
        ax1.set_ylabel('Absolute error')

        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=8, marker='^', alpha=0.5)
        ax2.plot(star_list, model_polyc_shpix_rel_rmse, **kwargs)
        ax2.set_ylabel('Relative error [%]')   
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + plot_dataset + '-metrics-' + run_id_no_suff + '_poly_pixel_3xResolution_RMSE.png'
        )
        plt.show()


def plot_optimisation_metrics(**args):
    r""" Plot optimisation results.
    """
    define_plot_style()

    # Define saving path
    plot_saving_path = args['base_path'] + args['plots_folder']

    # Define the number of datasets to test
    n_datasets = len(args['suffix_id_name'])

    optim_hist_file = args['base_path']  + args['optim_hist_folder']
    run_id_no_suff = args['model'] + args['base_id_name']

    # Define the metric data paths
    model_paths = [
        optim_hist_file + 'optim_hist_' + run_id_no_suff + _suff + '.npy'  
        for _suff in args['suffix_id_name']
    ]

    # Load metrics
    metrics = [
        np.load(_path, allow_pickle=True)[()]
        for _path in model_paths
    ]

    ## Plot the first parametric cycle
    cycle_str = 'param_cycle1'
    metric_str = 'mean_squared_error'
    val_mertric_str = 'val_mean_squared_error'

    fig = plt.figure(figsize=(12,8))
    ax1 = fig.add_subplot(111)
    for it in range(n_datasets):
        ax1.plot(
            metrics[0][cycle_str][metric_str],
            label=args['model'] + args['suffix_id_name'][it],
            alpha=0.75
        )
    plt.yscale('log')
    plt.minorticks_on()
    ax1.legend()
    ax1.set_title(
        'Parametric cycle 1.\n' + run_id_no_suff + '_' + cycle_str
        )
    ax1.set_xlabel('Number of epoch')
    ax1.set_ylabel('Training MSE')

    ax2 = ax1.twinx()
    kwargs = dict(linewidth=2, linestyle='dashed', markersize=2, marker='^', alpha=0.5)
    for it in range(n_datasets):
        ax2.plot(metrics[it][cycle_str][val_mertric_str], **kwargs)
    ax2.set_ylabel('Validation MSE')  
    ax2.grid(False)
    plt.savefig(
        plot_saving_path + 'optim_' + run_id_no_suff + '_' + cycle_str + '.png'
    )
    plt.show()

    # Plot the first non-parametric cycle
    if args['model'] != 'param':
        cycle_str = 'nonparam_cycle1'
        metric_str = 'mean_squared_error'
        val_mertric_str = 'val_mean_squared_error'

        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        for it in range(n_datasets):
            ax1.plot(
                metrics[it][cycle_str][metric_str],
                label=args['model'] + args['suffix_id_name'][it],
                alpha=0.75
            )
        plt.yscale('log')
        plt.minorticks_on()
        ax1.legend()
        ax1.set_title(
            'Non-parametric cycle 1.\n' + run_id_no_suff + '_' + cycle_str
        )
        ax1.set_xlabel('Number of epoch')
        ax1.set_ylabel('Training MSE')

        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=2, marker='^', alpha=0.5)
        for it in range(n_datasets):
            ax2.plot(metrics[it][cycle_str][val_mertric_str], **kwargs)
        ax2.set_ylabel('Validation MSE')  
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + 'optim_' + run_id_no_suff + '_' + cycle_str + '.png'
        )
        plt.show()


    ## Plot the second parametric cycle
    if cycle_str in metrics[0]:
        cycle_str = 'param_cycle2'
        metric_str = 'mean_squared_error'
        val_mertric_str = 'val_mean_squared_error'

        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        for it in range(n_datasets):
            ax1.plot(
                metrics[it][cycle_str][metric_str],
                label=args['model'] + args['suffix_id_name'][it],
                alpha=0.75
            )
        plt.yscale('log')
        plt.minorticks_on()
        ax1.legend()
        ax1.set_title(
            'Parametric cycle 2.\n' + run_id_no_suff + '_' + cycle_str
        )
        ax1.set_xlabel('Number of epoch')
        ax1.set_ylabel('Training MSE')

        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=2, marker='^', alpha=0.5)
        for it in range(n_datasets):
            ax2.plot(metrics[it][cycle_str][val_mertric_str], **kwargs)
        ax2.set_ylabel('Validation MSE')  
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + 'optim_' + run_id_no_suff + '_' + cycle_str + '.png'
        )
        plt.show()


    ## Plot the second non-parametric cycle
    if cycle_str in metrics[0]:
        cycle_str = 'nonparam_cycle2'
        metric_str = 'mean_squared_error'
        val_mertric_str = 'val_mean_squared_error'

        fig = plt.figure(figsize=(12,8))
        ax1 = fig.add_subplot(111)
        for it in range(n_datasets):
            ax1.plot(
                metrics[it][cycle_str][metric_str],
                label=args['model'] + args['suffix_id_name'][it],
                alpha=0.75
            )
        plt.yscale('log')
        plt.minorticks_on()
        ax1.legend()
        ax1.set_title(
            'Non-parametric cycle 2.\n' + run_id_no_suff + '_' + cycle_str
        )
        ax1.set_xlabel('Number of epoch')
        ax1.set_ylabel('Training MSE')

        ax2 = ax1.twinx()
        kwargs = dict(linewidth=2, linestyle='dashed', markersize=2, marker='^', alpha=0.5)
        for it in range(n_datasets):
            ax2.plot(metrics[it][cycle_str][val_mertric_str], **kwargs)

        ax2.set_ylabel('Validation MSE')  
        ax2.grid(False)
        plt.savefig(
            plot_saving_path + 'optim_' + run_id_no_suff + '_' + cycle_str + '.png'
        )
        plt.show()



def define_plot_style():
    # Define plot paramters
    plot_style = {
        'figure.figsize': (12,8),
        'figure.dpi': 200,
        'figure.autolayout':True,
        'lines.linewidth': 2,
        'lines.linestyle': '-',
        'lines.marker': 'o',
        'lines.markersize': 10,
        'legend.fontsize': 20,
        'legend.loc': 'best',
        'axes.titlesize': 24,
        'font.size': 16
    }
    mpl.rcParams.update(plot_style)
    # Use seaborn style
    sns.set()


def extract_poly_results(metrics_dicts, test_train='test'): 
    
    if test_train == 'test':
        first_key = 'test_metrics'
    elif test_train == 'train':
        first_key = 'train_metrics' 
    else:
        raise ValueError
        
    n_dicts = len(metrics_dicts)
    
    polyc_rmse = np.zeros(n_dicts)
    polyc_std_rmse = np.zeros(n_dicts)
    polyc_rel_rmse = np.zeros(n_dicts)
    polyc_std_rel_rmse = np.zeros(n_dicts)
    
    for it in range(n_dicts):
        polyc_rmse[it] = metrics_dicts[it][first_key]['poly_metric']['rmse']
        polyc_std_rmse[it] = metrics_dicts[it][first_key]['poly_metric']['std_rmse']
        polyc_rel_rmse[it] = metrics_dicts[it][first_key]['poly_metric']['rel_rmse']
        polyc_std_rel_rmse[it] = metrics_dicts[it][first_key]['poly_metric']['std_rel_rmse']

    return polyc_rmse, polyc_std_rmse, polyc_rel_rmse, polyc_std_rel_rmse
    

def extract_opd_results(metrics_dicts, test_train='test'): 
    
    if test_train == 'test':
        first_key = 'test_metrics'
    elif test_train == 'train':
        first_key = 'train_metrics' 
    else:
        raise ValueError
        
    n_dicts = len(metrics_dicts)
    
    opd_rmse = np.zeros(n_dicts)
    opd_std_rmse = np.zeros(n_dicts)
    opd_rel_rmse = np.zeros(n_dicts)
    opd_std_rel_rmse = np.zeros(n_dicts)
    
    for it in range(n_dicts):
        opd_rmse[it] = metrics_dicts[it][first_key]['opd_metric']['rmse_opd']
        opd_std_rmse[it] = metrics_dicts[it][first_key]['opd_metric']['rmse_std_opd']
        opd_rel_rmse[it] = metrics_dicts[it][first_key]['opd_metric']['rel_rmse_opd']
        opd_std_rel_rmse[it] = metrics_dicts[it][first_key]['opd_metric']['rel_rmse_std_opd']

    
    return opd_rmse, opd_std_rmse, opd_rel_rmse, opd_std_rel_rmse


def extract_shape_results(metrics_dicts, test_train='test'): 

    if test_train == 'test':
        first_key = 'test_metrics'
    elif test_train == 'train':
        first_key = 'train_metrics' 
    else:
        raise ValueError
        
    n_dicts = len(metrics_dicts)
    
    e1_rmse = np.zeros(n_dicts)
    e1_std_rmse = np.zeros(n_dicts)
    e1_rel_rmse = np.zeros(n_dicts)
    e1_std_rel_rmse = np.zeros(n_dicts)
    
    e2_rmse = np.zeros(n_dicts)
    e2_std_rmse = np.zeros(n_dicts)
    e2_rel_rmse = np.zeros(n_dicts)
    e2_std_rel_rmse = np.zeros(n_dicts)
    
    rmse_R2_meanR2 = np.zeros(n_dicts)
    std_rmse_R2_meanR2 = np.zeros(n_dicts)
    
    for it in range(n_dicts):
        e1_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['rmse_e1']
        e1_std_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['std_rmse_e1']
        e1_rel_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['rel_rmse_e1']
        e1_std_rel_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['std_rel_rmse_e1']
        
        e2_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['rmse_e2']
        e2_std_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['std_rmse_e2']
        e2_rel_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['rel_rmse_e2']
        e2_std_rel_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['std_rel_rmse_e2']
        
        rmse_R2_meanR2[it] = metrics_dicts[it][first_key]['shape_results_dict']['rmse_R2_meanR2']
        std_rmse_R2_meanR2[it] = metrics_dicts[it][first_key]['shape_results_dict']['std_rmse_R2_meanR2']

    e1 = [e1_rmse, e1_std_rmse, e1_rel_rmse, e1_std_rel_rmse]
    e2 = [e2_rmse, e2_std_rmse, e2_rel_rmse, e2_std_rel_rmse]
    R2 = [rmse_R2_meanR2, std_rmse_R2_meanR2]
    
    return e1, e2, R2
       

def extract_shape_pix_results(metrics_dicts, test_train='test'): 
    
    if test_train == 'test':
        first_key = 'test_metrics'
    elif test_train == 'train':
        first_key = 'train_metrics' 
    else:
        raise ValueError
        
    n_dicts = len(metrics_dicts)
    
    polyc_rmse = np.zeros(n_dicts)
    polyc_std_rmse = np.zeros(n_dicts)
    polyc_rel_rmse = np.zeros(n_dicts)
    polyc_std_rel_rmse = np.zeros(n_dicts)
    
    for it in range(n_dicts):
        polyc_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['pix_rmse']
        polyc_std_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['pix_rmse_std']
        polyc_rel_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['rel_pix_rmse']
        polyc_std_rel_rmse[it] = metrics_dicts[it][first_key]['shape_results_dict']['rel_pix_rmse_std']

    
    return polyc_rmse, polyc_std_rmse, polyc_rel_rmse, polyc_std_rel_rmse