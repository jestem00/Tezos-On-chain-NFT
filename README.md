Zero Contract

Zero reliance on off-chanin storage for our Tezos Art - Also a play on my name.

This smart contract has been writen to provide a simple way to mint on-chain artwork with the Tezos blockchain.
It is written in the Legacy SmartPy programming language speicifally for use with the legacy.smartpy.io/ide compiler.

There are two versions:
  v1 - This is simplified as much as possible. It is the original contract and is only suitable for 1/1
  v2 - This is a larger contract with a mix of v1 and the SmartPy FA2 template to ensure editions work properly

Author: jestemzero with assistance from ChatGPT, Gemini and Claude LLMs

xTwiiter / Warpcast / Discord: @jestemzero

IMPORTANT: On-chain artwork is saved with a datarUri format in the "artifactUri" metadata attribute.
Objkt.com currently does not recognize artifactUri strings longer than 254 characters.
Any token exceeding this limitation needs to contact Objkt.com directly and request the limitation be removed for their collection.

Current contracst include proposed Parent/Child relationship. These do not affect performance but can be deleted if desired.

Attribution appreciated but not required. Either way, if you end up using this contract I would love to hear about it.
I look forward to seeing the growth of Tezos on-chain art.
