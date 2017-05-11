#-*- coding: utf-8 -*-
'''
Created on 24 fevrier 2017

@author: SPU
'''

def calcul_des_chantiers(teneur = [0,0,0,0,4,3,3,0,0,3,4,5,2,0,0],
                         IC = 2,
                         OC = 3,
                         tc = 1,
                         print_all = 'N'):

    benefit, SV1, SV2, SV, SVP , SO1, SO2, SO, SOP, chantiers = [], [], [], [], [], [], [], [], [],[]
    
    for index in range(1,len(teneur)+1): benefit.append(teneur[index-1]-tc)

    for index in range(1,len(teneur)+1):
        
        SV.append('')
        SV1.append('')
        SV2.append('')
        SVP.append('')
        SO.append('')
        SO1.append('')
        SO2.append('')
        SOP.append('')
        chantiers.append('')
        
        if index < IC+OC:
            if index >= OC:
                SV[index-1] = 0
                for i in range(1,OC+1): SV[index-1] = SV[index-1]+benefit[index-1-OC+i]
            if index >= IC:
                SO[index-1] = 0
            if index == IC+OC-1:
                SVP[index-1], SOP[index-1] = IC, 1

        else:
            SV1[index-1] = benefit[index-1]+SV[index-2]
            SV2[index-1] = SO[index-1-OC]
            for i in range(0,OC):
                SV2[index-1] = SV2[index-1]+benefit[index-1-i]
            SV[index-1] = SV1[index-1] if SV1[index-1]>SV2[index-1] else SV2[index-1]
            
            SO1[index-1] = SO[index-2]
            SO2[index-1] = SV[index-1-IC]
            SO[index-1] = SO1[index-1] if SO1[index-1]>SO2[index-1] else SO2[index-1]

            if SO1[index-1]>SO2[index-1]:
                SOP[index-1] = SOP[index-2]
            else:
                SOP[index-1] = index-IC+1

            if SV1[index-1]>=SV2[index-1]:
                SVP[index-1] = SVP[index-2]
            else:
                SVP[index-1] = index-OC+1

    for index in range(len(teneur)-1, 0, -1):
        if index ==len(teneur)-1:
            debut_intercalaire = SOP[len(teneur)-1]
            fin_intercalaire = len(teneur)
            for i in range(debut_intercalaire, fin_intercalaire+1): chantiers[i-1]=0
            fin_chantier = SOP[len(teneur)-1]-1
            debut_chantier = SVP[fin_chantier-1]
            for i in range(debut_chantier, fin_chantier+1): chantiers[i-1]=1
        elif (isinstance(debut_chantier,int) and index == debut_chantier-1):
            debut_intercalaire = SOP[debut_chantier-2]
            fin_intercalaire = debut_chantier-1
            for i in range(debut_intercalaire, fin_intercalaire+1): chantiers[i-1]=0
            fin_chantier = debut_intercalaire-1
            debut_chantier = SVP[fin_chantier-1]
            if isinstance(debut_chantier,int):
                for i in range(debut_chantier, fin_chantier+1): chantiers[i-1]=1

    if print_all == 'Y':
        print 'teneur    ', teneur
        print 'benefit   ', benefit
        print 'SV1       ', SV1
        print 'SV2       ', SV2
        print 'SV        ', SV
        print 'SVP       ', SVP
        print 'SO1       ', SO1
        print 'SO2       ', SO2
        print 'SO        ', SO
        print 'SOP       ', SOP
        print 'chantiers ', chantiers

    return (chantiers)

def salissage(passes,
              longueur_salissage = 0):
  
#mesure en depth from/to

    for index in range(0, len(passes)): passes[index] = ([passes[index][0]-longueur_salissage, passes[index][1]+longueur_salissage, passes[index][2]])

    index = len(passes) if len(passes)==1 else 1

    while index <(len(passes)):
        while passes[index][0] < passes[index-1][0] and passes[index][2] == passes[index-1][2]:
#            print 'cas 1'
            del passes[index-1]
            index = index - 1
        if passes[index][0] < passes[index-1][1] and passes[index][2] == passes[index-1][2]:
#            print 'cas 2'
            passes[index][0] = passes[index-1][0]
            del passes[index-1]
            index = index - 1
        elif passes[index][0] < passes[index-1][1]:
#            print 'cas 3'
            demi_salissage = ((passes[index][0]+longueur_salissage) - (passes[index-1][1]-longueur_salissage))/2
            passes[index][0] = passes[index][0]+longueur_salissage-demi_salissage
            passes[index-1][1] = passes[index-1][1]-longueur_salissage+demi_salissage
        index = index + 1

    return passes

def main():
    passes = calcul_des_chantiers( print_all = 'Y')
    print '\n'
    passes = calcul_des_chantiers(teneur = [0,0,0,0,3,3,3,1,0,2,4,0,2,0,0], print_all = 'Y')
        
if __name__ == '__main__':
    main()



