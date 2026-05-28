#!/usr/bin/env python3
"""
DefiLlama SDK Explorer
Discovers all available methods, endpoints, and data structures
"""

import inspect
from defillama_sdk import DefiLlama
import json


def explore_client_methods(client):
    """Explore all methods available in the client"""
    print("=" * 60)
    print("🔍 EXPLORING DEFILLAMA SDK CLIENT")
    print("=" * 60)

    # Get all methods and attributes
    all_attrs = dir(client)

    # Filter out private methods (starting with _)
    public_methods = [attr for attr in all_attrs if not attr.startswith('_')]

    print(f"\n📦 Main Client Attributes/Methods ({len(public_methods)} total):")
    for method in public_methods:
        try:
            attr = getattr(client, method)
            if callable(attr):
                print(f"  ✅ {method}() - {type(attr).__name__}")
            else:
                print(f"  📁 {method} - {type(attr).__name__}")
        except (AttributeError, TypeError) as e:
            print(f"  ⚠️ {method} - (inaccessible: {e})")

    return public_methods


def explore_submodules(client, submodule_name):
    """Explore a specific submodule (like tvl, fees, etc.)"""
    print("\n" + "=" * 60)
    print(f"🔍 EXPLORING SUBMODULE: {submodule_name}")
    print("=" * 60)

    # Add None check at the beginning
    if client is None:
        print("❌ Client is None")
        return None

    if not hasattr(client, submodule_name):
        print(f"❌ Submodule '{submodule_name}' not found")
        return None

    submodule = getattr(client, submodule_name)
    submodule_methods = [m for m in dir(submodule) if not m.startswith('_')]

    print(f"\n📁 {submodule_name.upper()} Submodule Methods ({len(submodule_methods)} total):")

    methods_info = {}
    for method_name in submodule_methods:
        try:
            method = getattr(submodule, method_name)
            if callable(method):
                # Get method signature
                sig = inspect.signature(method)
                print(f"  ✅ {method_name}{sig}")

                # Try to get docstring
                doc = inspect.getdoc(method)
                if doc:
                    print(f"     📝 {doc[:100]}...")

                methods_info[method_name] = {
                    'signature': str(sig),
                    'docstring': doc[:200] if doc else None
                }
            else:
                print(f"  📁 {method_name} - {type(method).__name__}")
        except Exception as e:
            print(f"  ⚠️ {method_name} - Error: {e}")

    return methods_info


def test_api_call(method, *args, **kwargs):
    """Safely test an API call and return results"""
    if method is None:
        print("  ❌ Error: Method is None")
        return None

    try:
        result = method(*args, **kwargs)
        # Just return the result - don't check for Mock
        # If it's a Mock, that's a test issue, not production issue
        return result
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def explore_data_structure(data, name="Data", max_depth=2, current_depth=0):
    """Recursively explore data structure"""
    if current_depth >= max_depth:
        return

    indent = "  " * current_depth

    if isinstance(data, dict):
        print(f"{indent}📄 {name} (dict with {len(data)} keys)")
        if current_depth < max_depth:
            for key in list(data.keys())[:5]:  # Show first 5 keys
                value = data[key]
                value_type = type(value).__name__
                if isinstance(value, (dict, list)):
                    print(f"{indent}  🔑 '{key}': {value_type}({len(value)} items)")
                else:
                    preview = str(value)[:50]
                    print(f"{indent}  🔑 '{key}': {value_type} = {preview}...")
            if len(data) > 5:
                print(f"{indent}  ... and {len(data) - 5} more keys")
    elif isinstance(data, list):
        print(f"{indent}📋 {name} (list with {len(data)} items)")
        if current_depth < max_depth and len(data) > 0:
            explore_data_structure(
                data[0], "First item", max_depth, current_depth + 1
            )
    else:
        print(f"{indent}📊 {name}: {type(data).__name__} = {str(data)[:100]}")


def main():
    print("🚀 Initializing DefiLlama SDK...")
    client = DefiLlama()

    # 1. Explore main client
    main_methods = explore_client_methods(client)

    # 2. Look for common submodules
    potential_submodules = [
        'tvl', 'fees', 'revenue', 'yields', 'apy', 'lending', 'protocols', 'chains', 'tokens', 'liquidity', 'unlocks'
    ]

    available_submodules = []
    for sub in potential_submodules:
        if hasattr(client, sub):
            available_submodules.append(sub)
            print(f"\n✅ Found submodule: {sub}")

    # 3. Explore each available submodule
    submodule_methods = {}
    for sub in available_submodules:
        methods = explore_submodules(client, sub)
        if methods:
            submodule_methods[sub] = methods

    # 4. Test actual API calls to see data structure
    print("\n" + "=" * 60)
    print("🧪 TESTING ACTUAL API CALLS")
    print("=" * 60)

    # Test getting all protocols
    print("\n📡 Testing: client.tvl.getProtocols()")
    protocols = test_api_call(client.tvl.getProtocols)

    # Add type check
    if protocols and isinstance(protocols, list) and len(protocols) > 0:
        print(f"✅ Success! Retrieved {len(protocols)} protocols")
        print("\n📊 Sample protocol data structure:")

        # Find a lending protocol
        lending_protocols = [
            p for p in protocols if p.get('category') == 'Lending'
        ]
        if lending_protocols:
            sample = lending_protocols[0]
            print(f"\n  Example: {sample.get('name')}(Category: {sample.get('category')})")
            explore_data_structure(sample, "Protocol", max_depth=1)

            # Look for yield-related fields
            print("\n  🔎 Searching for yield/APY related fields:")
            yield_keywords = [
                'apy', 'yield', 'rate', 'interest', 'reward', 'borrow', 'supply'
            ]
            for key in sample.keys():
                for keyword in yield_keywords:
                    if keyword.lower() in key.lower():
                        print(f"    💰 Found: {key} = {sample[key]}")
                        break
        else:
            print("No lending protocols found in the response")
    else:
        if protocols is None:
            print("⚠️ API call returned None")
        elif not isinstance(protocols, list):
            print(f"⚠️ Expected list but got {type(protocols)}")
        else:
            print("⚠️ Empty list returned from getProtocols()")

    # Test getting specific protocol details
    print("\n📡 Testing: client.tvl.getProtocol('aave')")
    aave_details = test_api_call(client.tvl.getProtocol, 'aave')

    if aave_details and isinstance(aave_details, dict):  # Add type check here
        print("✅ Success! Retrieved Aave protocol details")
        print("\n📊 Aave data structure (top-level keys):")
        for key in aave_details.keys():
            print(f"  🔑 {key}: {type(aave_details[key]).__name__}")

            # Check for yield-related fields
            if any(
                kw in key.lower() for
                kw in ['apy', 'yield', 'rate', 'interest', 'reward']
            ):
                print("     💰 YIELD-RELATED FIELD FOUND!")
                explore_data_structure(aave_details[key], key, max_depth=1)
    else:
        if aave_details is None:
            print("⚠️ API call returned None")
        elif not isinstance(aave_details, dict):
            print(f"⚠️ Unexpected return type: {type(aave_details)}")

    # 5. Check for any yields or rates endpoints
    print("\n" + "=" * 60)
    print("🎯 SEARCHING FOR YIELD/APY ENDPOINTS")
    print("=" * 60)

    # Try common endpoint patterns
    test_endpoints = [
        ('client.get_yields', lambda: client.get_yields() if hasattr(client, 'get_yields') else None),
        ('client.yields', lambda: client.yields if hasattr(client, 'yields') else None),
        ('client.apy', lambda: client.apy if hasattr(client, 'apy') else None),
        ('client.tvl.get_yields', lambda: client.tvl.get_yields() if hasattr(client.tvl, 'get_yields') else None)
    ]

    for name, callable_func in test_endpoints:
        print(f"\n🔍 Checking {name}...")
        try:
            result = callable_func()
            if result:
                print(f"  ✅ FOUND! Result type: {type(result).__name__}")
                explore_data_structure(result, "Result", max_depth=1)
            else:
                print("  ⚠️ Not available or returned None")
        except AttributeError:
            print("  ❌ Attribute not found")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    # 6. Summary
    print("\n" + "=" * 60)
    print("📋 EXPLORATION SUMMARY")
    print("=" * 60)
    print(f"""
    ✅ Available Submodules: {', '.join(available_submodules)}

    📊 Data Retrieved:
    - Total Protocols: {len(protocols) if protocols else 0}
    - Lending Protocols: {len(lending_protocols) if 'lending_protocols' in locals() else 0}

    💡 Recommendations:
    1. Use client.tvl.getProtocols() to list all lending platforms
    2. Use client.tvl.getProtocol('protocol-name') for detailed data
    3. Check the GitHub repo for undocumented yield endpoints
    4. Consider using the Pro API for yield-specific data

    📚 Next Steps:
    - Explore the fees/revenue endpoints (likely where yields live)
    - Check the MCP server mentioned in documentation
    - Look at direct protocol APIs (Aave, Compound) for precise APY data
    """)

    # Save exploration results to file
    with open('sdk_exploration_results.json', 'w') as f:
        json.dump({
            'available_submodules': available_submodules,
            'protocols_count': len(protocols) if protocols else 0,
            'sample_protocol': sample if 'sample' in locals() else None,
        }, f, indent=2, default=str)

    print("\n💾 Exploration results saved to 'sdk_exploration_results.json'")


if __name__ == "__main__":
    main()
