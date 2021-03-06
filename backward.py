import numpy as np
from PIL import Image
import tensorflow as tf
from time import sleep
import os
from time import sleep
import forward
import generateds
from tqdm import tqdm, trange

BATCH_SIZE = 1
L1_WEIGHT = 50
GAN_WEIGHT = 1
GUIDE_DECODER_WEIGHT = 1
EPS = 1e-12
LEARNING_RATE = 2e-04
BETA1 = 0.5
EMA_DECAY = 0.98
PARAMS = 'l1weight={},gfc={}, mcl={} with guide decoder'.format(L1_WEIGHT, forward.FIRST_OUTPUT_CHANNEL, forward.MAX_OUTPUT_CHANNEL_LAYER)
MODEL_SAVE_PATH = 'model_{}'.format(PARAMS)
MODEL_NAME = 'pix2pix_model'
TOTAL_STEP = 200000 
TRAINING_RESULT_PATH = 'training_result_{}'.format(PARAMS)
GUIDE_DECODER_PATH = 'guide_decoder_{}'.format(PARAMS)
SAVE_FREQ = 1000
DISPLAY_FREQ = 100
DISPLAY_GUIDE_DECODER_FREQ = 100 

def backward():
    def dis_conv(X, kernels, stride, layer, regularizer=None):
        initializer = tf.truncated_normal_initializer(0, 0.2)
        w = tf.get_variable('w{}'.format(layer), [forward.KERNEL_SIZE, forward.KERNEL_SIZE, X.get_shape().as_list()[-1], kernels], initializer=initializer)
        padded_X = tf.pad(X, [[0, 0], [1, 1], [1, 1], [0, 0]], mode='CONSTANT')
        return tf.nn.conv2d(padded_X, w, [1, stride, stride, 1], padding='VALID')

    def discriminator(discriminator_input, discriminator_output):
        X = tf.concat([discriminator_input, discriminator_output], axis=3)
        layers = [X]
        for i in range(6):
            stride = 2 if i < 4 else 1
            kernels = forward.FIRST_OUTPUT_CHANNEL / 2 * 2 ** i if i < 5 else 1
            activation_fn = forward.lrelu if i < 5 else tf.nn.sigmoid
            bn = forward.batchnorm if i < 5 else tf.identity
            layers.append(activation_fn(bn(dis_conv(layers[-1], kernels, stride, i+1))))
        return layers[-1]
    
    def guide_decoder(middle_layer, batch_size):
        layers = [middle_layer]
        for i in range(5):
            deconvolved = forward.gen_deconv(layers[-1], forward.FIRST_OUTPUT_CHANNEL * 2 ** min(forward.MAX_OUTPUT_CHANNEL_LAYER, 4 - i), batch_size)
            output = forward.batchnorm(deconvolved)
            output = forward.lrelu(output)
            layers.append(output)
        output = forward.gen_deconv(output, 3, batch_size)
        output = tf.nn.tanh(output)
        layers.append(output)
        return layers[-1]

    X = tf.placeholder(tf.float32, [None, None, None, 3])
    with tf.name_scope('generator'), tf.variable_scope('generator'):
        Y, middle_layer = forward.forward(X, BATCH_SIZE, True)
        Y_guide = guide_decoder(middle_layer, BATCH_SIZE)
    Y_real = tf.placeholder(tf.float32, [None, None, None, 3])
    XYY = tf.concat([X, Y, Y_real], axis=2)
    
    with tf.name_scope('discriminator_real'):
        with tf.variable_scope('discriminator'):
            discriminator_real = discriminator(X, Y_real)

    with tf.name_scope('discriminator_fake'):
        with tf.variable_scope('discriminator', reuse=True):
            discriminator_fake = discriminator(X, Y)

    dis_loss = tf.reduce_mean(-tf.log(discriminator_real + EPS) -tf.log(1 - discriminator_fake + EPS))
    dis_vars = [var for var in tf.trainable_variables() if var.name.startswith('discriminator')]
    dis_optimizer = tf.train.AdamOptimizer(LEARNING_RATE, BETA1)
    dis_train_op = dis_optimizer.minimize(dis_loss, var_list=dis_vars)

    gen_loss_GAN = tf.reduce_mean(-tf.log(discriminator_fake + EPS))
    gen_loss_L1 = tf.reduce_mean(tf.abs(Y - Y_real))
    guide_decoder_loss =  tf.reduce_mean(tf.abs(Y_guide - Y_real))
    gen_loss = L1_WEIGHT * (gen_loss_L1 + GUIDE_DECODER_WEIGHT * guide_decoder_loss) + GAN_WEIGHT * gen_loss_GAN
    #gen_loss = L1_WEIGHT * gen_loss_L1 + GAN_WEIGHT * gen_loss_GAN
    gen_vars = [var for var in tf.trainable_variables() if var.name.startswith('generator')]
    gen_optimizer = tf.train.AdamOptimizer(LEARNING_RATE, BETA1)
    gen_train_op = gen_optimizer.minimize(gen_loss, var_list=gen_vars)

    #ema = tf.train.ExponentialMovingAverage(EMA_DECAY)
    #ema_op = ema.apply(tf.trainable_variables())

    global_step = tf.Variable(0, trainable=False)
    incr_global_step = tf.assign(global_step, global_step + 1) 

    #train_op = tf.group([dis_train_op, gen_train_op, ema_op, incr_global_step])
    train_op = tf.group([dis_train_op, gen_train_op, incr_global_step])
    gen_vars = [var for var in tf.trainable_variables() if var.name.startswith('generator')]

    saver = tf.train.Saver()
    X_batch, Y_real_batch = generateds.get_tfrecord(BATCH_SIZE, True)

    if not os.path.exists(MODEL_SAVE_PATH):
        os.mkdir(MODEL_SAVE_PATH)
    if not os.path.exists(TRAINING_RESULT_PATH):
        os.mkdir(TRAINING_RESULT_PATH)
    if not os.path.exists(GUIDE_DECODER_PATH):
        os.mkdir(GUIDE_DECODER_PATH)

    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())

        ckpt = tf.train.get_checkpoint_state(MODEL_SAVE_PATH)
        if ckpt and ckpt.model_checkpoint_path:
            saver.restore(sess, ckpt.model_checkpoint_path)

        coord = tf.train.Coordinator()
        threads = tf.train.start_queue_runners(sess=sess, coord=coord)

        for i in range(global_step.eval(), TOTAL_STEP):
            xs, ys = sess.run([X_batch, Y_real_batch])
            _, step = sess.run([train_op, global_step], feed_dict={X:xs, Y_real:ys})
            for i in range(4):
                sess.run(gen_train_op, feed_dict={X:xs, Y_real:ys})
            #print(sess.run(discriminator_real, feed_dict={X:xs, Y_real:ys}))
            #sleep(30)
            if step % SAVE_FREQ == 0:
                saver.save(sess, os.path.join(MODEL_SAVE_PATH, MODEL_NAME), global_step=global_step)
            if step % DISPLAY_FREQ == 0:
                #glloss, gdloss, ggloss, dloss = sess.run([gen_loss_L1, guide_decoder_loss, gen_loss_GAN, dis_loss], feed_dict={X:xs, Y_real:ys})
                glloss, ggloss, dloss = sess.run([gen_loss_L1, gen_loss_GAN, dis_loss], feed_dict={X:xs, Y_real:ys})
                print('\rSteps: {}, Generator L1 loss: {:.6f}, Generator GAN loss: {:.6f}, Discriminator loss: {:.6f}'.format(step, glloss , ggloss, dloss))
                test_result = sess.run(XYY, feed_dict={X:xs, Y_real:ys})
                for i, img in enumerate(test_result[:3]):
                    img = (img + 1) / 2
                    img *= 256
                    img = img.astype(np.uint8)
                    Image.fromarray(img).save(os.path.join(TRAINING_RESULT_PATH, 'Step{}-{}.png'.format(step, i+1)))
            if step % DISPLAY_GUIDE_DECODER_FREQ == 0:
                guide_result = sess.run(Y_guide, feed_dict={X:xs, Y_real:ys})
                #print('\rSteps: {}, Guide loss: {}'.format(step, guide_loss))
                for i, img in enumerate(guide_result[:1]):
                    img = (img + 1) / 2
                    img *= 256
                    img = img.astype(np.uint8)
                    Image.fromarray(img).save(os.path.join(GUIDE_DECODER_PATH, 'Step-{}.png'.format(step)))
            print('\r{}'.format(step), end='')

        coord.request_stop()
        coord.join(threads)


if __name__ == '__main__':
    backward()

