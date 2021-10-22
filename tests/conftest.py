from collections import namedtuple
from scripts.helpers.test_pools import create_eth_pool, create_pool, create_token
from brownie import MockRouter
from lixir.system import (
    LixirSystem,
    VaultDeployParameters,
    deploy_dependencies,
    get_accounts,
)
import pytest

@pytest.fixture(scope="module", autouse=True)
def shared_setup(module_isolation):
    pass


@pytest.fixture(scope="session")
def UniswapV3Core(pm):
    UniswapV3Core = pm("Uniswap/uniswap-v3-core@1.0.0")
    return UniswapV3Core


@pytest.fixture(scope="module")
def lixir_accounts(accounts):
    return get_accounts()


@pytest.fixture(scope="module")
def gov(lixir_accounts):
    return lixir_accounts.gov


@pytest.fixture(scope="module")
def delegate(lixir_accounts):
    return lixir_accounts.delegate


@pytest.fixture(scope="module")
def strategist(lixir_accounts):
    return lixir_accounts.strategist


@pytest.fixture(scope="module")
def keeper(lixir_accounts):
    return lixir_accounts.keeper


@pytest.fixture(scope="module")
def deployer(lixir_accounts):
    return lixir_accounts.deployer


@pytest.fixture(scope="module")
def pauser(lixir_accounts):
    return lixir_accounts.pauser


@pytest.fixture(scope="module")
def uni_gov(accounts):
    return accounts[6]


@pytest.fixture(scope="module")
def users(accounts):
    return accounts[7:]


@pytest.fixture(scope="module")
def user(users):
    return users[0]


@pytest.fixture(scope="module")
def system(uni_gov, lixir_accounts):
    weth, uni_factory = deploy_dependencies(uni_gov)
    system = LixirSystem.deploy(weth, uni_factory, lixir_accounts)
    return system


@pytest.fixture(scope="module")
def registry(system):
    return system.registry


@pytest.fixture(scope="module")
def vault_impl(system):
    return system.vault_impl


@pytest.fixture(scope="module")
def eth_vault_impl(system):
    return system.eth_vault_impl


@pytest.fixture(scope="module")
def strat_simp_gwap(system):
    return system.strat_simp_gwap


@pytest.fixture(scope="module")
def factory(system):
    return system.factory


@pytest.fixture(scope="module")
def uni_factory(system):
    return system.uni_factory


@pytest.fixture(scope="module")
def weth(system):
    return system.weth


@pytest.fixture(scope="module")
def pool(uni_factory, users, mock_router):
    tokenA = create_token("TokenA", "TA")
    tokenB = create_token("TokenB", "TokenB")
    pool = create_pool(uni_factory, tokenA, tokenB, users, 3000)
    spacing = pool.pool.tickSpacing()
    tick = 887271 // spacing * spacing
    mock_router.mintAmounts(pool.pool, 1e18, 1e18, -tick, tick)
    return pool


@pytest.fixture(scope="module")
def eth_pool(weth, uni_factory, users):
    tokenA = create_token("TokenA", "TA")
    eth_pool = create_eth_pool(uni_factory, tokenA, weth, users, 3000)
    return eth_pool


@pytest.fixture(scope="module")
def vault(
    pool, strategist, users, mock_router, system: LixirSystem,
):
    vault = system.deploy_vault(
        VaultDeployParameters(
            name="Lixir Vault Token",
            symbol="LVT",
            tokenA=pool.token0,
            tokenB=pool.token1,
            fee=pool.fee,
            tick_short_duration=60,
            max_tick_diff=120,
            main_spread=1800,
            range_spread=900,
        )
    )
    for u in users:
        pool.token0.approve(vault, 2 ** 256 - 1, {"from": u})
        pool.token1.approve(vault, 2 ** 256 - 1, {"from": u})
        pool.token0.approve(mock_router, 2 ** 256 - 1, {"from": u})
        pool.token1.approve(mock_router, 2 ** 256 - 1, {"from": u})
    vault.setPerformanceFee(0, {"from": strategist})
    return vault


@pytest.fixture(scope="module")
def eth_vault(eth_pool, strategist, users, system: LixirSystem):
    vault = system.deploy_eth_vault(
        VaultDeployParameters(
            name="Lixir Vault Token",
            symbol="LVT",
            tokenA=eth_pool.token0,
            tokenB=eth_pool.token1,
            fee=eth_pool.fee,
            tick_short_duration=60,
            max_tick_diff=120,
            main_spread=1800,
            range_spread=900,
        )
    )
    for u in users:
        eth_pool.token0.approve(vault, 2 ** 256 - 1, {"from": u})
        eth_pool.token1.approve(vault, 2 ** 256 - 1, {"from": u})
    vault.setPerformanceFee(0, {"from": strategist})
    return vault


@pytest.fixture(scope="module")
def mock_router(uni_gov):
    mock_router = MockRouter.deploy({'from': uni_gov})
    return mock_router
