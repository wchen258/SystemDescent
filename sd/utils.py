from tensorflow import keras
from tensorflow.keras import layers
import tensorflow as tf
import math
import pickle
import numpy as np
import os
import uuid
from pathlib import Path
# from tqdm_note import tqdm
import time
from tqdm.autonotebook import tqdm
from typing import TypedDict, Optional, Callable, Any
from . import dfl

def map_dict_elems(fn, d):
    return {k: fn(d[k]) for k in d.keys()}


def to_numpy(tensor):
    return tf.make_ndarray(tf.make_tensor_proto(tensor))

def latest_subdir(dir="."):
    with_paths = map(lambda subdir: dir + "/" + subdir, os.listdir(dir))
    sub_dirs = filter(os.path.isdir, with_paths)
    return max(sub_dirs, key=os.path.getmtime)

def random_subdir(location):
    uniq_id = uuid.uuid1().__str__()[:6]
    folder_path = Path(location, uniq_id)
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

def save_checkpoint(path, model, id, extra_objs=None):
    checkpoint_path = Path(path, "checkpoints", f"checkpoint{id}")
    checkpoint_path.mkdir(parents=True, exist_ok=True)
    print("saving: ", str(checkpoint_path))
    model.save(str(checkpoint_path))
    with open(str(checkpoint_path)+"/extra_objs.pb", "wb") as f:
        pickle.dump(extra_objs, f)

def load_checkpoint(path):
    custom_objects= pickle.load(open(path+"/extra_objs.pb", "rb"))
    return keras.models.load_model(path, custom_objects={"SaveMe":custom_objects})
    

def latest_model():
    latest_env = latest_subdir("models")
    latest_run = latest_subdir(latest_env)
    latest_checkpoint = latest_subdir(latest_run + "/checkpoints")
    print(f"using model {latest_checkpoint}")
    return latest_checkpoint

def extract_env_name(checkpoint_path):
    return Path(checkpoint_path).parent.parent.parent.name


def desc_line():
    desc_line_pb = tqdm(bar_format="[{desc}]")
    def update_description(desc):
        desc_line_pb.update()
        desc_line_pb.set_description(desc)
    return update_description, desc_line_pb

def np_dict_to_dict_generator(d: dict):
    size = min(map(len, d.values()))
    iterator_dict = dict(map(lambda kv: (kv[0], iter(kv[1])), d.items()))
    def next_in_dict():
        return dict(map(lambda k: (k,next(iterator_dict[k])), d.keys()))
    return map(lambda i: next_in_dict(), range(size))

def map_dict(f, d):
    return dict(map(lambda kv: (kv[0], f(kv[1])), d.items()))

class FreqAndCallback(TypedDict):
    freq: int
    callback: Callable[[int], Any]

def train_loop(list_of_batches, train_step, every_n_seconds:Optional[FreqAndCallback]=None, end_of_epoch=None):
    time_at_reset = time.time()
    for epoch, batches in enumerate(list_of_batches):
        print(f"\nStart of epoch {epoch}")
        epoch_time = time.time()
        if isinstance(batches, dict):
            batches = np_dict_to_dict_generator(batches)
        # num_batches = len(batches)
        # iterator = iter(batches)
        with tqdm(batches) as pb:
            update_description, desc_pb = desc_line()
            with desc_pb:
                for batch in pb:
                    if every_n_seconds:
                        if(time.time() - time_at_reset > every_n_seconds["freq"]):
                            every_n_seconds["callback"](epoch)
                            time_at_reset = time.time()
                    update_description(train_step(batch))


        if end_of_epoch:
            end_of_epoch(epoch)

        print(f"Time taken: {(time.time() - epoch_time):.2f}s")


def mean_grad_size(grads):
    return sum(map(lambda grad_bundle: tf.norm(tf.abs(grad_bundle)), filter(lambda grad_bundle: not(grad_bundle is None),grads)))/len(grads)


@tf.keras.utils.register_keras_serializable(package='Custom', name='p_mean')
class PMean(tf.keras.regularizers.Regularizer):
    def __init__(self, p=1.):
        self.p = p

    def __call__(self, x):
        return dfl.p_mean(x, self.p)

    def get_config(self):
        return {'p': float(self.p)}