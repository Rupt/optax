# Copyright 2023 DeepMind Technologies Limited. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Tests for `reduce_on_plateau.py`."""

from absl.testing import absltest
from absl.testing import parameterized
import chex
from jax import config
import jax.numpy as jnp
from optax import contrib


class ReduceLROnPlateauTest(parameterized.TestCase):
  """Test for reduce_on_plateau scheduler."""

  def setUp(self):
    super().setUp()
    self.patience = 5
    self.cooldown = 5
    self.transform = contrib.reduce_on_plateau(
        factor=0.1,
        patience=self.patience,
        threshold=1e-4,
        cooldown=self.cooldown,
    )
    self.updates = {'params': jnp.array(1.0)}  # dummy updates

  def tearDown(self):
    super().tearDown()
    config.update('jax_enable_x64', False)

  @parameterized.parameters(False, True)
  def test_learning_rate_reduced_after_cooldown_period_is_over(
      self, enable_x64
  ):
    """Test that learning rate is reduced after cooldown."""

    # Enable float64 if requested
    config.update('jax_enable_x64', enable_x64)

    # Initialize the state
    state = self.transform.init(self.updates['params'])

    # Wait until patience runs out
    for _ in range(self.patience + 1):
      updates, state = self.transform.update(
          updates=self.updates, state=state, loss=1.0
      )

    # Check that learning rate is reduced
    lr, best_loss, plateau_count, cooldown_counter = state
    chex.assert_trees_all_close(lr, 0.1)
    chex.assert_trees_all_close(best_loss, 1.0)
    chex.assert_trees_all_close(plateau_count, 0)
    chex.assert_trees_all_close(cooldown_counter, self.cooldown)
    chex.assert_trees_all_close(updates, {'params': jnp.array(0.1)})

    # One more step
    _, state = self.transform.update(updates=updates, state=state, loss=1.0)

    # Check that cooldown_counter is decremented
    lr, best_loss, plateau_count, cooldown_counter = state
    chex.assert_trees_all_close(lr, 0.1)
    chex.assert_trees_all_close(best_loss, 1.0)
    chex.assert_trees_all_close(plateau_count, 0)
    chex.assert_trees_all_close(cooldown_counter, self.cooldown - 1)

  @parameterized.parameters(False, True)
  def test_learning_rate_is_not_reduced(self, enable_x64):
    """Test that plateau_count resets after a new best_loss is found."""

    # Enable float64 if requested
    config.update('jax_enable_x64', enable_x64)

    # State with positive plateau_count
    state = contrib.ReduceLROnPlateauState(
        best_loss=jnp.array(1.0, dtype=jnp.float32),
        plateau_count=jnp.array(3, dtype=jnp.int32),
        lr=jnp.array(0.1, dtype=jnp.float32),
        cooldown_counter=jnp.array(0, dtype=jnp.int32),
    )

    # Update with better loss
    _, new_state = self.transform.update(
        updates=self.updates, state=state, loss=0.1
    )

    # Check that plateau_count resets
    lr, best_loss, plateau_count, _ = new_state
    chex.assert_trees_all_close(plateau_count, 0)
    chex.assert_trees_all_close(lr, 0.1)
    chex.assert_trees_all_close(best_loss, 0.1)

  @parameterized.parameters(False, True)
  def test_learning_rate_not_reduced_during_cooldown(self, enable_x64):
    """Test that learning rate is not reduced during cooldown."""

    # Enable float64 if requested
    config.update('jax_enable_x64', enable_x64)

    # State with positive cooldown_counter
    state = contrib.ReduceLROnPlateauState(
        best_loss=jnp.array(1.0, dtype=jnp.float32),
        plateau_count=jnp.array(0, dtype=jnp.int32),
        lr=jnp.array(0.1, dtype=jnp.float32),
        cooldown_counter=jnp.array(3, dtype=jnp.int32),
    )

    # Update with worse loss
    _, new_state = self.transform.update(
        updates=self.updates, state=state, loss=2.0
    )

    # Check that learning rate is not reduced and
    # plateau_count is not incremented
    lr, best_loss, plateau_count, cooldown_counter = new_state
    chex.assert_trees_all_close(lr, 0.1)
    chex.assert_trees_all_close(best_loss, 1.0)
    chex.assert_trees_all_close(plateau_count, 0)
    chex.assert_trees_all_close(cooldown_counter, 2)


if __name__ == '__main__':
  absltest.main()
