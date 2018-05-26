"""Unit tests for //deeplearning/clgen/model.py."""
import sys

import checksumdir
import pytest
from absl import app

from deeplearning.clgen import errors
from deeplearning.clgen.models import models
from deeplearning.clgen.proto import internal_pb2
from deeplearning.clgen.proto import model_pb2
from lib.labm8 import crypto
from lib.labm8 import pbutil


class MockSampler(object):
  """Mock class for a Sampler."""

  # The default value for start_text has been chosen to only use characters and
  # words from the abc_corpus, so that it may be encoded using the vocabulary
  # of that corpus.
  def __init__(self, start_text: str = 'H', hash='hash'):
    self.start_text = start_text
    self.hash = hash


# The Model.hash for a Model instance of abc_model_config.
ABC_MODEL_HASH = '98dadcd7890565e65be97ac212a141a744e8b016'


def test_Model_hash(clgen_cache_dir, abc_model_config):
  """Test that the ID of a known corpus matches expected value."""
  del clgen_cache_dir
  m = models.Model(abc_model_config)
  assert ABC_MODEL_HASH == m.hash


def test_Model_config_hash_different_options(clgen_cache_dir, abc_model_config):
  """Test that model options produce different model hashes."""
  del clgen_cache_dir
  abc_model_config.architecture.neuron_type = model_pb2.NetworkArchitecture.GRU
  m1 = models.Model(abc_model_config)
  abc_model_config.architecture.neuron_type = model_pb2.NetworkArchitecture.RNN
  m2 = models.Model(abc_model_config)
  assert m1.hash != m2.hash


def test_Model_config_hash_different_num_epochs(clgen_cache_dir,
                                                abc_model_config):
  """Test that different num_eopchs doesn't affect model hash."""
  del clgen_cache_dir
  abc_model_config.training.num_epochs = 10
  m1 = models.Model(abc_model_config)
  abc_model_config.training.num_epochs = 20
  m2 = models.Model(abc_model_config)
  assert m1.hash == m2.hash


def test_Model_config_hash_different_corpus(clgen_cache_dir, abc_model_config):
  """Test that different corpuses produce different model hashes."""
  del clgen_cache_dir
  abc_model_config.corpus.sequence_length = 5
  m1 = models.Model(abc_model_config)
  abc_model_config.corpus.sequence_length = 10
  m2 = models.Model(abc_model_config)
  assert m1.hash != m2.hash


def test_Model_equality(clgen_cache_dir, abc_model_config):
  """Test that two corpuses with identical options are equivalent."""
  del clgen_cache_dir
  m1 = models.Model(abc_model_config)
  m2 = models.Model(abc_model_config)
  assert m1 == m2


def test_Model_inequality(clgen_cache_dir, abc_model_config):
  """Test that two corpuses with different options are not equivalent."""
  del clgen_cache_dir
  abc_model_config.architecture.num_layers = 1
  m1 = models.Model(abc_model_config)
  abc_model_config.architecture.num_layers = 2
  m2 = models.Model(abc_model_config)
  assert m1 != m2


def test_Model_metafile(clgen_cache_dir, abc_model_config):
  """Test that a newly instantiated model has a metafile."""
  del clgen_cache_dir
  m = models.Model(abc_model_config)
  assert (m.cache.path / 'META.pbtxt').is_file()
  assert pbutil.ProtoIsReadable(m.cache.path / 'META.pbtxt',
                                internal_pb2.ModelMeta())


# TODO(cec): Add tests on ModelMeta contents.


def test_Model_epoch_checkpoints_untrained(clgen_cache_dir, abc_model_config):
  """Test that an untrained model has no checkpoint files."""
  del clgen_cache_dir
  m = models.Model(abc_model_config)
  assert not m.epoch_checkpoints


# Model.Train() tests.


def test_Model_is_trained(clgen_cache_dir, abc_model_config):
  """Test that is_trained changes to True when model is trained."""
  del clgen_cache_dir
  m = models.Model(abc_model_config)
  assert not m.is_trained
  m.Train()
  assert m.is_trained


def test_Model_is_trained_new_instance(clgen_cache_dir, abc_model_config):
  """Test that is_trained is True on a new instance of a trained model."""
  del clgen_cache_dir
  m1 = models.Model(abc_model_config)
  m1.Train()
  m2 = models.Model(abc_model_config)
  assert m2.is_trained


def test_Model_Train_epoch_checkpoints(clgen_cache_dir, abc_model_config):
  """Test that a trained model has a TensorFlow checkpoint."""
  del clgen_cache_dir
  abc_model_config.training.num_epochs = 2
  m = models.Model(abc_model_config)
  m.Train()
  assert len(m.epoch_checkpoints) == 2
  for path in m.epoch_checkpoints:
    assert path.is_file()


def test_Model_Train_twice(clgen_cache_dir, abc_model_config):
  """Test that TensorFlow checkpoint does not change after training twice."""
  del clgen_cache_dir
  abc_model_config.training.num_epochs = 1
  m = models.Model(abc_model_config)
  m.Train()
  f1a = checksumdir.dirhash(m.cache.path / 'checkpoints')
  f1b = crypto.md5_file(m.cache.path / 'META.pbtxt')
  m.Train()
  f2a = checksumdir.dirhash(m.cache.path / 'checkpoints')
  f2b = crypto.md5_file(m.cache.path / 'META.pbtxt')
  assert f1a == f2a
  assert f1b == f2b


# TODO(cec): Add tests on incrementally trained model predictions and losses.

# Model.Sample() tests.


def test_Model_Sample_invalid_start_text(clgen_cache_dir, abc_model_config):
  """Test that InvalidStartText error raised if start text cannot be encoded."""
  del clgen_cache_dir
  m = models.Model(abc_model_config)
  with pytest.raises(errors.InvalidStartText):
    # This start_text chosen to include characters not in the abc_corpus.
    m.Sample(MockSampler(start_text='!@#1234'), 1)


def test_Model_Sample_implicit_train(clgen_cache_dir, abc_model_config):
  """Test that Sample() implicitly trains the model."""
  del clgen_cache_dir
  m = models.Model(abc_model_config)
  assert not m.is_trained
  m.Sample(MockSampler(), 1)
  assert m.is_trained


def test_Model_Sample_return_value_matches_cached_sample(clgen_cache_dir,
                                                         abc_model_config):
  """Test that Sample() returns Sample protos."""
  del clgen_cache_dir
  m = models.Model(abc_model_config)
  samples = m.Sample(MockSampler(hash='hash'), 1)
  assert len(samples) == 1
  assert len((m.cache.path / 'samples' / 'hash').iterdir()) == 1
  cached_sample_path = (m.cache.path / 'samples' / 'hash' / (
    (m.cache.path / 'samples' / 'hash').iterdir()[0]))
  cached_sample = pbutil.FromFile(cached_sample_path, internal_pb2.Sample())
  assert samples[0].text == cached_sample.text
  assert samples[0].sample_time_ms == cached_sample.sample_time_ms
  assert samples[
           0].sample_start_epoch_ms_utc == cached_sample.sample_start_epoch_ms_utc


@pytest.mark.skip(reason='TODO(cec): Implement!')
def test_Model_Sample_one_sample(clgen_cache_dir, abc_model_config):
  """Test that Sample() produces the expected number of samples."""
  del clgen_cache_dir
  m = models.Model(abc_model_config)
  m.Train()
  abc_sampler_config.min_num_samples = 1
  s = samplers.Sampler(abc_sampler_config)
  # Take a single sample.
  s.Sample(m)
  num_contentfiles = len(fs.ls(s.cache(m)["samples"]))
  # Note that the number of contentfiles may be larger than 1, even though we
  # asked for a single sample, since we split the output on the start text.
  assert num_contentfiles >= 1
  s.Sample(m)
  num_contentfiles2 = len(fs.ls(s.cache(m)["samples"]))
  assert num_contentfiles == num_contentfiles2


@pytest.mark.skip(reason='TODO(cec): Implement!')
def test_Model_Sample_five_samples(clgen_cache_dir, abc_corpus_config):
  del clgen_cache_dir
  m = models.Model(abc_corpus_config)
  m.Train()
  abc_sampler_config.min_num_samples = 5
  s = samplers.Sampler(abc_sampler_config)
  s.Sample(m)
  num_contentfiles = len(fs.ls(s.cache(m)["samples"]))
  assert num_contentfiles >= 5


def main(argv):
  """Main entry point."""
  if len(argv) > 1:
    raise app.UsageError('Unrecognized command line flags.')
  sys.exit(pytest.main([__file__, '-v']))


if __name__ == '__main__':
  app.run(main)