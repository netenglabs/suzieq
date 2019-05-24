#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

name = "sqengines"

from .base_engine import get_sqengine

__all__ = [get_sqengine]
