from brownie import LixirVault, LixirVaultETH
from eth_abi import encode_abi

def deploy_vault(
    deployer,
    name,
    symbol,
    tokenA,
    tokenB,
    factory,
    strategist,
    keeper,
    vault_impl,
    strat_simp_gwap,
    fee,
    tick_short_duration,
    max_tick_diff,
    main_spread,
    range_spread,
    eth=False,
):
    args = (
        name,
        symbol,
        tokenA,
        tokenB,
        vault_impl,
        strategist,
        keeper,
        strat_simp_gwap,
        encode_abi(
            ["uint24", "uint32", "int24", "int24", "int24"],
            [fee, tick_short_duration, max_tick_diff, main_spread, range_spread],
        ),
    )
    if eth:
        tx = factory.createVaultETH(*(args + ({"from": deployer, "gas": 2000000},)))
        vault = LixirVaultETH.at(tx.new_contracts[0])
    else:
        tx = factory.createVault(*(args + ({"from": deployer, "gas": 2000000},)))
        vault = LixirVault.at(tx.new_contracts[0])
    return vault
