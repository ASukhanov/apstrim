# aplog
Application for logging Control System parameters and data objects to file. Analog of SDDS writer.

- Supported infrastructures: ADO, EPICS, LITE.
- Efficient binary serialization format.
- Like JSON. But it's faster and smaller.
- Numpy arrays supported.
- Optional online compression.

## Examples

  :python -m aplog -nEPICS -oScope1_MeanValue testAPD:scope1:MeanValue_RBV
  21-06-02 13:10:43 Logged 61 paragraphs, 1.36 KBytes
  ...

  :python -m aplog -nEPICS  --compress -oScope1_MeanValue testAPD:scope1:MeanValue_RBV
  21-06-02 13:20:47 Logged 61 paragraphs, 1.058 KBytes
  ...

  :python -m aplog -nLITE acnlin23:dev1:cycle
  21-06-02 13:30:31 Logged 5776 paragraphs, 103.986 KBytes
  ...

  :python -m aplog -nLITE --compress acnlin23:dev1:cycle
  21-06-02 13:40:41 Logged 5767 paragraphs, 54.456 KBytes
  ...

  :python -m aplog -nLITE acnlin23:dev1:cycle acnlin23:dev1:y
  pars: {'acnlin23:dev1:cycle': ['0'], 'acnlin23:dev1:y': ['1']}
  21-06-02 13:50:14 Logged 5763 paragraphs, 46448.658 KBytes
  ...



