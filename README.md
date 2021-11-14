# Diabetic-Retinopathy-Scoring-Using-GANs
Final project for the BioInformatics exam at Politecnico di Torino about **Diabetic-Retinopathy-Scoring-Using-GANs**.

## Team members
- Abbamonte Matteo (_matteoabbamonte_)
- Koudounas Alkis (_koudounasalkis_)

## Contents
- Diabetic Retinopathy Detection Dataset
- Retinopathy Sample Generation via GANs
- Feature Extraction
- Linear Regressors & Cross-Validation 
- Linear Regressors & Performance Evaluation

## Report, slides and code 
You can find our report and the usage manual [here](https://github.com/koudounasalkis/Diabetic-Retinopathy-Scoring-Using-GANs/blob/main/Report_Manual_BioInformatics_Project9_Abbamonte_Koudounas.pdf).

Our presentation slides are [here](https://github.com/koudounasalkis/Diabetic-Retinopathy-Scoring-Using-GANs/blob/main/Presentation_BioInformatics_Project9_Abbamonte_Koudounas.pdf).

All our code is in a Python Notebook format, you can explore it [here](https://github.com/koudounasalkis/Diabetic-Retinopathy-Scoring-Using-GANs/blob/main/BioInformatics_Project.ipynb).

## Experiments Manual Structure
```
PRESETS
    Import Libraries                    # Imports the packages necessary for each experiment
    Utils                               # Includes several functions useful for the feature extraction phase
DIABETIC RETINOPATHY DETECTION DATASET  # Contains the sequence of commands that allowed us to download the original dataset, decompress it, prepareit and build it
RETINOPATHY SAMPLE GENERATION
    Load Dataset for GAN Training       # Builds and batch the dataset that is pre-saved in the mounted gdrive partition
    First GAN / Second GAN              # Can be run to build the model, restore the latest checkpoint for the corresponding GAN and finally obtain a newimage, that will be plotted
FEATURE EXTRACTION                      # Each subsection includes a call to a function for restoring the chosen GAN and build the features extractor model starting from it, as well as the code for performing the features extraction itself
CROSS-VALIDATION                        # Includes the features extraction phase (by means of the best performing GAN model for the extractor itself), and a stratified 5-fold cross-validation process based on the main linear regression models that have been analyzed, namely SKLearn, Analytical Optimization and Keras Dense Layer
LINEAR REGRESSION                       # Contains the code for building the two best Linear Regression models analyzed (the one based on SKLearn and the other that uses the analytical optimization), and their performance evaluation
```
