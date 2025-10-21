#!/usr/bin/env python3
"""Locate the ADOMD.NET library path in the local NuGet cache.

Search order: net8.0, net6.0, netstandard2.0, net48, net472, net471, net47
Prints the first matching lib directory path, or an error token starting with NO_.
"""
import os
import sys


def find_adomd_lib() -> str | None:
    home = os.path.expanduser("~")
    base = os.path.join(home, ".nuget", "packages", "microsoft.analysisservices.adomdclient")
    if not os.path.isdir(base):
        return None

    try:
        versions = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
        versions.sort(reverse=True)
        tfms = ("net8.0", "net6.0", "netstandard2.0", "net48", "net472", "net471", "net47")
        for ver in versions:
            for tfm in tfms:
                p = os.path.join(base, ver, "lib", tfm)
                if os.path.isdir(p) and os.path.isfile(os.path.join(p, "Microsoft.AnalysisServices.AdomdClient.dll")):
                    return p
    except Exception:
        return None
    return None


if __name__ == "__main__":
    path = find_adomd_lib()
    if path:
        print(path)
        sys.exit(0)
    else:
        print("NO_ADOMD_PATH")
        sys.exit(1)
