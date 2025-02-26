# Release Notes

_Generated on 2025-02-26 18:41:42_

Period: last-month


## Summary of Changes


### 2025-02-20 - keboola.ex-franconnect 0.0.8

**Component:** [keboola.ex-franconnect](https://github.com/component-franconnect)  
**Tag:** [0.0.8](https://github.com/keboola/component-franconnect/releases/tag/0.0.8)  
**Previous Tag:** 0.0.7




#### Changes:

- flatten termination endpoint data ([a7f944b](https://github.com/keboola/component-franconnect/commit/a7f944b45a72d9b0508528070346a3cd867cffab))

- Merge pull request #5 from keboola/feature/SUPPORT-10843-flatten ([6105907](https://github.com/keboola/component-franconnect/commit/6105907983dd27cfb6f656223cd4f83de5f24b90))




#### Files Changed:
- 1 files modified
- 0 added
- 1 modified
- 0 removed


**Modified Files:**

- src/component.py (modified, +1, -1)





### 2025-02-20 - keboola.ex-franconnect 0.0.7

**Component:** [keboola.ex-franconnect](https://github.com/component-franconnect)  
**Tag:** [0.0.7](https://github.com/keboola/component-franconnect/releases/tag/0.0.7)  
**Previous Tag:** 0.0.6




#### Changes:

- flatten agreement endpoint data ([c3ade87](https://github.com/keboola/component-franconnect/commit/c3ade871bb2f88d60fdf7977c8efcd24478ce5bc))

- Merge pull request #4 from keboola/feature/flatten-data-SUPPORT-10843 ([334669e](https://github.com/keboola/component-franconnect/commit/334669e1f40519933c20ce68ac062c4953f01cd9))




#### Files Changed:
- 1 files modified
- 0 added
- 1 modified
- 0 removed


**Modified Files:**

- src/component.py (modified, +11, -1)





### 2025-02-12 - keboola.ex-franconnect 0.0.6

**Component:** [keboola.ex-franconnect](https://github.com/component-franconnect)  
**Tag:** [0.0.6](https://github.com/keboola/component-franconnect/releases/tag/0.0.6)  
**Previous Tag:** 0.0.5




#### Changes:

- Update franconnect.py ([39a8ff9](https://github.com/keboola/component-franconnect/commit/39a8ff9479582f5039a9bc2ce537d71f3eec945e))

- Merge pull request #3 from keboola/fix/auth-url ([1be5c3e](https://github.com/keboola/component-franconnect/commit/1be5c3e83ecd7d7e60efb6af84111ab2362a00d0))




#### Files Changed:
- 1 files modified
- 0 added
- 1 modified
- 0 removed


**Modified Files:**

- src/client/franconnect.py (modified, +1, -1)





### 2025-02-10 - keboola.ex-franconnect 0.0.5

**Component:** [keboola.ex-franconnect](https://github.com/component-franconnect)  
**Tag:** [0.0.5](https://github.com/keboola/component-franconnect/releases/tag/0.0.5)  
**Previous Tag:** 0.0.4




#### Changes:

- fix response can be dict instead of list of dict, properly raising exception ([d43f5cd](https://github.com/keboola/component-franconnect/commit/d43f5cd352a21253d3beb2f6637054481e9c194a))

- Fix line length ([15e4420](https://github.com/keboola/component-franconnect/commit/15e4420b76c4bbdd13b3dc53a18400ac4bc7b9f1))

- Merge pull request #2 from keboola/fix/response ([2ec2f94](https://github.com/keboola/component-franconnect/commit/2ec2f949a14dddc500dfe494e474991212e6444f))




#### Files Changed:
- 2 files modified
- 0 added
- 2 modified
- 0 removed


**Modified Files:**

- src/client/franconnect.py (modified, +8, -0)

- src/component.py (modified, +1, -1)





### 2025-01-30 - keboola.ex-franconnect 0.0.4

**Component:** [keboola.ex-franconnect](https://github.com/component-franconnect)  
**Tag:** [0.0.4](https://github.com/keboola/component-franconnect/releases/tag/0.0.4)  
**Previous Tag:** 0.0.2




#### Changes:

- config - added default value (for sync actions), fix UI, fix test connection ([c9ba137](https://github.com/keboola/component-franconnect/commit/c9ba137e789fedac453ac0813128cab8b487c8dd))

- implemented requested changes ([8f18ef6](https://github.com/keboola/component-franconnect/commit/8f18ef617f36459a11829b4b7aff641206da298f))

- Merge pull request #1 from keboola/fix/finalization ([a445343](https://github.com/keboola/component-franconnect/commit/a4453436315e447462a2dcb88b3d224c7b6da7a2))




#### Files Changed:
- 4 files modified
- 0 added
- 4 modified
- 0 removed


**Modified Files:**

- component_config/configRowSchema.json (modified, +1, -21)

- src/client/franconnect.py (modified, +12, -8)

- src/component.py (modified, +3, -4)

- src/configuration.py (modified, +5, -5)





### 2025-01-29 - keboola.ex-franconnect 0.0.3

**Component:** [keboola.ex-franconnect](https://github.com/component-franconnect)  
**Tag:** [0.0.3](https://github.com/keboola/component-franconnect/releases/tag/0.0.3)  
**Previous Tag:** 0.0.1




#### Changes:

- UI fix ([08122e5](https://github.com/keboola/component-franconnect/commit/08122e59249713628b5a1979c2a117ec47a5da5b))

- config edit ([d077c9a](https://github.com/keboola/component-franconnect/commit/d077c9a5863b5a5d75850761d1f4f27694510f35))

- config edit ([2febff3](https://github.com/keboola/component-franconnect/commit/2febff3c0beac8614a054892871aa2c99d6ef07c))

- pipeline test setup + component edit ([ed29b15](https://github.com/keboola/component-franconnect/commit/ed29b15621ec0375aaf51f2468e9cda6ea1425fb))

- last updates ([e0253b1](https://github.com/keboola/component-franconnect/commit/e0253b10a59cbcd49e3983a31f671b2c8a76b455))

- client - fix auth, added methods get_modules and get_submodules for sync actions, added pagination to get_data ([801e7ab](https://github.com/keboola/component-franconnect/commit/801e7aba7d3faf0baaee6b1da8303923e8166fee))

- change configuration structure, component.py added sync actions, saving data to table, requirements.txt ([803ff44](https://github.com/keboola/component-franconnect/commit/803ff44dc557b8e961734d529ea89218d30ebc08))

- fix ([306416e](https://github.com/keboola/component-franconnect/commit/306416ecf02c7f983038c708d2a3c5e7304b4bf8))

- UI, example config, readme ([0b62683](https://github.com/keboola/component-franconnect/commit/0b6268360b215f9bad766c80bef3f030f4f34881))

- GH pipeline ([2bb2b07](https://github.com/keboola/component-franconnect/commit/2bb2b07bfa9fbefba69358a78760e07e936d4490))

- config - added default value (for sync actions), fix UI, fix test connection ([c9ba137](https://github.com/keboola/component-franconnect/commit/c9ba137e789fedac453ac0813128cab8b487c8dd))




#### Files Changed:
- 11 files modified
- 1 added
- 8 modified
- 2 removed





### 2025-01-29 - keboola.ex-franconnect 0.0.2

**Component:** [keboola.ex-franconnect](https://github.com/component-franconnect)  
**Tag:** [0.0.2](https://github.com/keboola/component-franconnect/releases/tag/0.0.2)  
**Previous Tag:** 0.0.3




#### Changes:

- config - added default value (for sync actions), fix UI, validation_result type ([5542ce7](https://github.com/keboola/component-franconnect/commit/5542ce784a5b6b2e966b89eb7d752bdd8ffa04bc))




#### Files Changed:
- 3 files modified
- 0 added
- 3 modified
- 0 removed


**Modified Files:**

- component_config/configRowSchema.json (modified, +1, -19)

- src/component.py (modified, +2, -2)

- src/configuration.py (modified, +5, -5)





 