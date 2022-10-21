L and C components not included because of copyright

e.g. you can download some [here]([MLCCs | Passive Bauelemente | Würth Elektronik Produktkatalog](https://www.we-online.com/katalog/de/WCAP-CSRF#/articles/WCAP-CSRF-0402))

## Important
The directory structure is as follows:

- `series/` contains all measurements that will be used in series configuration
- `shunt/` contains all measurements that will be used in shunt configuration
- each of these directories should have subdirectories with the relevant `s2p` files
  - the name of these directories does not matter. however, inside each directory every file has to have the same frequency data (i.e. should be from one series of measurements)
    - if they have different frequencies, put them in different folders
  - the name **does matter** for the situation below
- **if you want to use a series measurement in shunt configuration you will have to prefix the measurement subdirectory inside the shunt folder with 'series'**
  - example:
    - components/
      - series/
        - C-murata/
          - abc.s2p
          - xyz.s2p
          - ...
        - L/
          - lmn.s2p
          - opq.s2p
          - ...
      - shunt/
        - C/
          - 123.s2p
          - ...
        - series_C-murata/
          - abc.s2p
          - xyz.s2p
          - ...
    - this is important because otherwise the series files will be put into the wrong topology and mess up the simulation
