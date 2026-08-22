"""LLM Council backend package."""

# Use the OS certificate store instead of certifi's bundle. Required on
# machines behind TLS-inspecting security software or a corporate proxy,
# where the interception root CA is trusted by the OS but absent from
# certifi - httpx otherwise fails every request with CERTIFICATE_VERIFY_FAILED.
# Must run before any ssl.SSLContext is created, hence package import time.
import truststore

truststore.inject_into_ssl()
