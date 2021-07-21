import numpy as np
import tensorflow as tf
from wf_psf.tf_psf_field import build_PSF_model



class L1ParamScheduler(tf.keras.callbacks.Callback):
    """L1 rate scheduler which sets the L1 rate according to schedule.

  Arguments:
      l1_schedule_rule: a function that takes an epoch index
          (integer, indexed from 0) and current l1_rate
          as inputs and returns a new l1_rate as output (float).
  """

    def __init__(self, l1_schedule_rule):
        super(L1ParamScheduler, self).__init__()
        self.l1_schedule_rule = l1_schedule_rule

    def on_epoch_begin(self, epoch, logs=None):
        # Get the current learning rate from model's optimizer.
        l1_rate = float(tf.keras.backend.get_value(self.model.l1_rate))
        # Call schedule function to get the scheduled learning rate.
        scheduled_l1_rate = self.l1_schedule_rule(epoch, l1_rate)
        # Set the value back to the optimizer before this epoch starts
        self.model.set_l1_rate(scheduled_l1_rate)
        # tf.keras.backend.set_value(self.model.optimizer.lr, scheduled_lr)

def l1_schedule_rule(epoch_n, l1_rate):
    if epoch_n!= 0 and epoch_n%10 == 0:
        scheduled_l1_rate = l1_rate/2
        print("\nEpoch %05d: L1 rate is %0.4e." % (epoch_n, scheduled_l1_rate))
        return scheduled_l1_rate
    else:
        return l1_rate


def general_train_cycle(tf_semiparam_field, inputs, outputs,
                val_data, batch_size,
                l_rate_param, l_rate_non_param,
                n_epochs_param, n_epochs_non_param,
                param_optim=None, non_param_optim=None,
                param_loss=None, non_param_loss=None,
                param_metrics=None, non_param_metrics=None,
                param_callback=None, non_param_callback=None,
                general_callback=None, first_run=False,
                verbose=1):
    """ Function to do a BCD iteration on the model.
    
    Define the model optimisation.

    For the parametric part we are using:
    ``l_rate_param = 1e-2``, ``n_epochs_param = 20``.
    For the non-parametric part we are using:
    ``l_rate_non_param = 1.0``, ``n_epochs_non_param = 100``.
    
    Parameters
    ----------
    TODO..

    Returns
    -------
    tf_semiparam_field: tf.keras.Model
        Trained Tensorflow model.
    hist_param: Tensorflow's History object
        History of the parametric training.
    hist_non_param: Tensorflow's History object
        History of the non-parametric training.

    """
    # Parametric train

    # Define Loss
    if param_loss is None:
        loss = tf.keras.losses.MeanSquaredError()
    else:
        loss = param_loss

    # Define optimiser
    if param_optim is None:
        optimizer = tf.keras.optimizers.Adam(
            learning_rate=l_rate_param, beta_1=0.9, beta_2=0.999,
            epsilon=1e-07, amsgrad=False)
    else:
        optimizer = param_optim

    # Define metrics
    if param_metrics is None:
        metrics = [tf.keras.metrics.MeanSquaredError()]
    else:
        metrics = param_metrics

    # Define callbacks
    if param_callback is None and general_callback is None:
        callbacks = None
    else:
        if general_callback is None:
            callbacks = param_callback
        elif param_callback is None:
            callbacks = general_callback
        else:
            callbacks = general_callback + param_callback

    # If it is the first run
    if first_run:
        # Set the non-parametric model to zero
        # With alpha to zero its already enough
        tf_semiparam_field.set_zero_nonparam()

    # Set the trainable layer
    tf_semiparam_field.set_trainable_layers(param_bool=True, nonparam_bool=False)

    # Compile the model for the first optimisation
    tf_semiparam_field = build_PSF_model(tf_semiparam_field,
                                         optimizer=optimizer,
                                         loss=loss,
                                         metrics=metrics)

    # Train the parametric part
    print('Starting parametric update..')
    hist_param = tf_semiparam_field.fit(x = inputs,
                                        y = outputs,
                                        batch_size = batch_size,
                                        epochs = n_epochs_param,
                                        validation_data = val_data,
                                        callbacks = callbacks,
                                        verbose = verbose)

    ## Non parametric train

    # If it is the first run
    if first_run:
        # Set the non-parametric model to non-zero
        # With alpha to zero its already enough
        tf_semiparam_field.set_nonzero_nonparam()

    # Set the non parametric layer to non trainable
    tf_semiparam_field.set_trainable_layers(param_bool=False, nonparam_bool=True)


    # Define Loss
    if non_param_loss is None:
        loss = tf.keras.losses.MeanSquaredError()
    else:
        loss = non_param_loss

    # Define optimiser
    if non_param_optim is None:
        optimizer = tf.keras.optimizers.Adam(
            learning_rate=l_rate_non_param, beta_1=0.9, beta_2=0.999,
            epsilon=1e-07, amsgrad=False)
    else:
        optimizer = non_param_optim

    # Define metric
    if non_param_metrics is None:
        metrics = [tf.keras.metrics.MeanSquaredError()]
    else:
        metrics = non_param_metrics

    # Define callbacks
    if non_param_callback is None and general_callback is None:
        callbacks = None
    else:
        if general_callback is None:
            callbacks = non_param_callback
        elif non_param_callback is None:
            callbacks = general_callback
        else:
            callbacks = general_callback + non_param_callback

    # Compile the model again for the second optimisation
    tf_semiparam_field = build_PSF_model(tf_semiparam_field,
                                         optimizer=optimizer,
                                         loss=loss,
                                         metrics=metrics)

    # Train the parametric part
    print('Starting non-parametric update..')
    hist_non_param = tf_semiparam_field.fit(x = inputs,
                                            y = outputs,
                                            batch_size = batch_size,
                                            epochs = n_epochs_non_param,
                                            validation_data = val_data,
                                            callbacks = callbacks,
                                            verbose = verbose)

    return tf_semiparam_field, hist_param, hist_non_param


def first_train_cycle(tf_semiparam_field, inputs, outputs, batch_size,
                      l_rate_param, l_rate_non_param,
                      n_epochs_param, n_epochs_non_param,
                      param_optim=None, non_param_optim=None,
                      param_loss=None, non_param_loss=None,
                      param_metrics=None, non_param_metrics=None,
                      param_callback=None, non_param_callback=None,
                      verbose=1):

    ## First parametric train

    # Define the model optimisation
    # l_rate_param = 1e-2
    # n_epochs_param = 20
    if param_loss is None:
        loss = tf.keras.losses.MeanSquaredError()
    else:
        loss = param_loss

    if param_optim is None:
        optimizer = tf.keras.optimizers.Adam(
            learning_rate=l_rate_param, beta_1=0.9, beta_2=0.999,
            epsilon=1e-07, amsgrad=False)
    else:
        optimizer = param_optim

    if param_metrics is None:
        metrics = [tf.keras.metrics.MeanSquaredError()]
    else:
        metrics = param_metrics

    # Set the non-parametric model to zero
    # With alpha to zero its already enough
    tf_semiparam_field.set_zero_nonparam()

    # Set the non parametric layer to non trainable
    # And keep the parametric layer to trainable
    tf_semiparam_field.set_trainable_layers(param_bool=True, nonparam_bool=False)


    # Compile the model for the first optimisation
    tf_semiparam_field = build_PSF_model(tf_semiparam_field, optimizer=optimizer,
                                                    loss=loss, metrics=metrics)

    # Train the parametric part
    print('Starting parametric update..')
    history_param = tf_semiparam_field.fit(x=inputs, y=outputs,
                                           batch_size=batch_size,
                                           epochs=n_epochs_param,
                                           callbacks=param_callback,
                                           verbose=verbose)


    ## Non parametric train
    # Set the non-parametric model to non-zero
    # With alpha to zero its already enough
    tf_semiparam_field.set_nonzero_nonparam()

    # Set the non parametric layer to non trainable
    # Set the parametric layer to non trainable
    tf_semiparam_field.set_trainable_layers(param_bool=False, nonparam_bool=True)


    # Non parametric parameters
    # l_rate_non_param = 1.0
    # n_epochs_non_param = 100

    # Define the model optimisation
    if non_param_loss is None:
        loss = tf.keras.losses.MeanSquaredError()
    else:
        loss = non_param_loss

    if non_param_optim is None:
        optimizer = tf.keras.optimizers.Adam(
            learning_rate=l_rate_non_param, beta_1=0.9, beta_2=0.999,
            epsilon=1e-07, amsgrad=False)
    else:
        optimizer = non_param_optim

    if non_param_metrics is None:
        metrics = [tf.keras.metrics.MeanSquaredError()]
    else:
        metrics = non_param_metrics


    # Compile the model again for the second optimisation
    tf_semiparam_field = build_PSF_model(tf_semiparam_field, optimizer=optimizer,
                                                    loss=loss, metrics=metrics)

    # Train the parametric part
    print('Starting non-parametric update..')
    history_non_param = tf_semiparam_field.fit(x=inputs, y=outputs,
                                               batch_size=batch_size,
                                               epochs=n_epochs_non_param,
                                               callbacks=non_param_callback,
                                               verbose=verbose)


    return tf_semiparam_field, history_param, history_non_param


def train_cycle(tf_semiparam_field, inputs, outputs, batch_size,
                l_rate_param, l_rate_non_param,
                n_epochs_param, n_epochs_non_param,
                param_optim=None, non_param_optim=None,
                param_loss=None, non_param_loss=None,
                param_metrics=None, non_param_metrics=None,
                param_callback=None, non_param_callback=None,
                verbose=1):

    ## Parametric train

    # Define the model optimisation
    # l_rate_param = 1e-2
    # n_epochs_param = 20
    if param_loss is None:
        loss = tf.keras.losses.MeanSquaredError()
    else:
        loss = param_loss

    if param_optim is None:
        optimizer = tf.keras.optimizers.Adam(
            learning_rate=l_rate_param, beta_1=0.9, beta_2=0.999,
            epsilon=1e-07, amsgrad=False)
    else:
        optimizer = param_optim

    if param_metrics is None:
        metrics = [tf.keras.metrics.MeanSquaredError()]
    else:
        metrics = param_metrics

    # Set the trainable layer
    tf_semiparam_field.set_trainable_layers(param_bool=True, nonparam_bool=False)

    # Compile the model for the first optimisation
    tf_semiparam_field = build_PSF_model(tf_semiparam_field, optimizer=optimizer,
                                                    loss=loss, metrics=metrics)

    # Train the parametric part
    print('Starting parametric update..')
    history_param = tf_semiparam_field.fit(x=inputs, y=outputs,
                                           batch_size=batch_size,
                                           epochs=n_epochs_param,
                                           callbacks=param_callback,
                                           verbose=verbose)

    ## Non parametric train
    # Set the non parametric layer to non trainable
    tf_semiparam_field.set_trainable_layers(param_bool=False, nonparam_bool=True)

    # Non parametric parameters
    # l_rate_non_param = 1.0
    # n_epochs_non_param = 100

    # Define the model optimisation
    if non_param_loss is None:
        loss = tf.keras.losses.MeanSquaredError()
    else:
        loss = non_param_loss

    if non_param_optim is None:
        optimizer = tf.keras.optimizers.Adam(
            learning_rate=l_rate_non_param, beta_1=0.9, beta_2=0.999,
            epsilon=1e-07, amsgrad=False)
    else:
        optimizer = non_param_optim

    if non_param_metrics is None:
        metrics = [tf.keras.metrics.MeanSquaredError()]
    else:
        metrics = non_param_metrics

    # Compile the model again for the second optimisation
    tf_semiparam_field = build_PSF_model(tf_semiparam_field, optimizer=optimizer,
                                                    loss=loss, metrics=metrics)

    # Train the parametric part
    print('Starting non-parametric update..')
    history_non_param = tf_semiparam_field.fit(x=inputs, y=outputs,
                                               batch_size=batch_size,
                                               epochs=n_epochs_non_param,
                                               callbacks=non_param_callback,
                                               verbose=verbose)

    return tf_semiparam_field, history_param, history_non_param
