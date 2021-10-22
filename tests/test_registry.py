import pytest

def test_registry(
    accounts,
    registry,
    gov,
    delegate,
    strategist,
    keeper,
    deployer,
    pauser,
    weth,
    uni_factory,
):
    gov_role = registry.gov_role()
    assert registry.weth9() == weth.address
    assert registry.uniV3Factory() == uni_factory.address
    assert registry.isGovOrDelegate(gov)
    assert registry.isGovOrDelegate(delegate)
    for x in (v for v in accounts if (v != gov and v != delegate)):
        assert not registry.isGovOrDelegate(x)
    assert registry.hasRole(gov_role, gov)
    for x in (v for v in accounts if v != gov):
        assert not registry.hasRole(gov_role, x)
    delegate_role = registry.delegate_role()
    assert registry.hasRole(delegate_role, delegate)
    for x in (v for v in accounts if v != delegate):
        assert not registry.hasRole(delegate_role, x)
    strategist_role = registry.strategist_role()
    assert registry.hasRole(strategist_role, strategist)
    for x in (v for v in accounts if v != strategist):
        assert not registry.hasRole(strategist_role, x)
    keeper_role = registry.keeper_role()
    assert registry.hasRole(keeper_role, keeper)
    for x in (v for v in accounts if v != keeper):
        assert not registry.hasRole(keeper_role, x)
    deployer_role = registry.deployer_role()
    assert registry.hasRole(deployer_role, deployer)
    for x in (v for v in accounts if v != deployer):
        assert not registry.hasRole(deployer_role, x)
    pauser_role = registry.pauser_role()
    assert registry.hasRole(pauser_role, pauser)
    for x in (v for v in accounts if v != pauser):
        assert not registry.hasRole(pauser_role, x)


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass
