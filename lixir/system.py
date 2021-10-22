from collections import namedtuple
from brownie import (
    LixirRegistry,
    LixirFactory,
    LixirVault,
    LixirVaultETH,
    LixirStrategySimpleGWAP,
)


LixirSystem = namedtuple(
    "LixirSystem",
    ["registry", "factory", "vault_impl", "eth_vault_impl", "strat_simp_gwap"],
)


def deploy_system(
    uni_factory,
    weth,
    gov,
    delegate,
    strategist,
    pauser,
    keeper,
    deployer,
):
    registry = delegate.deploy(LixirRegistry, gov, delegate, uni_factory, weth)
    registry.grantRole(registry.strategist_role(), strategist)
    registry.grantRole(registry.fee_setter_role(), strategist)
    registry.grantRole(registry.pauser_role(), pauser)
    registry.grantRole(registry.keeper_role(), keeper)
    registry.grantRole(registry.deployer_role(), deployer)
    factory = delegate.deploy(LixirFactory, registry)
    vault_impl = delegate.deploy(LixirVault, registry)
    eth_vault_impl = delegate.deploy(LixirVaultETH, registry)
    strat_simp_gwap = delegate.deploy(LixirStrategySimpleGWAP, registry)
    registry.grantRole(registry.factory_role(), factory)
    registry.grantRole(registry.vault_implementation_role(), vault_impl)
    registry.grantRole(registry.eth_vault_implementation_role(), eth_vault_impl)
    registry.grantRole(registry.strategy_role(), strat_simp_gwap)
    return LixirSystem(registry, factory, vault_impl, eth_vault_impl, strat_simp_gwap)
