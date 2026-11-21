# MicroMetropolis sponsor synchronization

This repository publishes the VRChat world's read-only roster to GitHub Pages. The world checks `roster.txt` once a minute. GitHub Actions checks Afdian every 15 minutes. Edits saved through the local sponsor manager also request a run. GitHub's scheduler and CDN can add delay.

The API credential and the operator's compressed configuration are encrypted GitHub Actions secrets. The workflow publishes only player-name lookup digests, tiers, expiry timestamps and optional wall credits. Display-name digests are pseudonyms and can be matched against a known name. No order details, raw binding codes or unpublished VRChat names are included in the Pages artifact.

Only a complete, validated Afdian response and matching operator configuration can deploy a new roster. A failed run leaves the previous deployment intact. The monthly health marker keeps the scheduled public repository active. The workflow has no pull-request trigger.

