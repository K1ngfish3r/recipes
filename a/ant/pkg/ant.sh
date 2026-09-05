#!/usr/bin/env sh
# SPDX-FileCopyrightText: 2026 AerynOS Developers
# SPDX-License-Identifier: MPL-2.0

# OpenJDK is installed as versioned binaries (java-25, etc.); Ant expects
# JAVA_HOME/bin/java or an unversioned java on PATH.
export JAVA_HOME="${JAVA_HOME:-/usr/lib/openjdk-25}"
exec /usr/share/ant/bin/ant "$@"
