from brownie import web3

def position_key(address, tickLower, tickUpper):
    return web3.keccak(int(address, 16).to_bytes(20,'big') + tickLower.to_bytes(3, 'big') + tickUpper.to_bytes(3, 'big'))
