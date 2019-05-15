#!/usr/bin/env python3

# Copyright (c) Dinesh G Dutt.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
#

from os.path import dirname, basename, isfile, join
import glob

name = "sqobjects"

modules = glob.glob(join(dirname(__file__), "*.py"))
__all__ = [basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]

